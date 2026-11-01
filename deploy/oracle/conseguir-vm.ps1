<#
.SYNOPSIS
    Reintenta crear la VM gratuita de Oracle Cloud (VM.Standard.A1.Flex) hasta que haya cupo.

.DESCRIPTION
    Oracle responde "Out of host capacity" cuando no quedan máquinas ARM gratuitas en la zona. Este script lo
    reintenta solo, rotando por las zonas (availability domains) de tu región, hasta que una acepte.

    Busca por su cuenta la imagen de Ubuntu 24.04 ARM y una subred pública. Si no hay subred, crea la red
    (VCN, internet gateway, ruta y subred) y abre los puertos 80 y 443 para la web. Es seguro volver a correrlo:
    si la VM ya existe, no crea otra; solo muestra su IP.

    Requisitos: OCI CLI instalado y configurado con una API key (ver docs/despliegue.md, "Oracle Cloud gratis").

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File deploy\oracle\conseguir-vm.ps1

.EXAMPLE
    # Si tras un día no hay cupo, pedir una máquina más pequeña (también gratis) suele entrar antes:
    powershell -ExecutionPolicy Bypass -File deploy\oracle\conseguir-vm.ps1 -Ocpus 1 -MemoriaGb 6
#>
[CmdletBinding()]
param(
    [string]$ClavePublica = (Join-Path $HOME '.ssh\id_ed25519.pub'),
    [string]$Nombre = 'dragones',
    [ValidateRange(1, 4)][int]$Ocpus = 2,
    [ValidateRange(1, 24)][int]$MemoriaGb = 12,
    [ValidateRange(50, 200)][int]$DiscoGb = 100,
    [ValidateRange(30, 3600)][int]$EsperaSegundos = 60,
    [string]$Perfil = 'DEFAULT'
)

$ErrorActionPreference = 'Stop'
# En Windows la CLI avisa que los permisos del archivo de configuración son "muy abiertos"; ensucia la salida.
$env:OCI_CLI_SUPPRESS_FILE_PERMISSIONS_WARNING = 'True'
$Forma = 'VM.Standard.A1.Flex'
$temporales = New-Object System.Collections.Generic.List[string]

function Escribir([string]$texto, [string]$color = 'Gray') {
    Write-Host ("[{0:HH:mm:ss}] {1}" -f (Get-Date), $texto) -ForegroundColor $color
}

function Detener([string]$texto) {
    Escribir $texto 'Red'
    exit 1
}

# Llama a la CLI. Separa la salida (JSON) de los errores para poder leer ambos.
function Invocar-Oci([string[]]$Argumentos) {
    $archivoError = [IO.Path]::GetTempFileName()
    $anterior = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $salida = & oci @Argumentos --profile $Perfil 2> $archivoError
        $codigo = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $anterior
    }
    $detalle = "$(Get-Content -Raw $archivoError)"
    Remove-Item $archivoError -ErrorAction SilentlyContinue
    # PowerShell 5.1 envuelve cada línea de error con su propia decoración (posición, CategoryInfo...): se quita.
    $detalle = (($detalle -split "`r?`n") | Where-Object {
            $_.Trim() -and $_ -notmatch '^\s*(\+|At |En |CategoryInfo|FullyQualifiedErrorId)'
        }) -join "`n" -replace '(?m)^oci\s*:\s*', ''
    $texto = ($salida | Out-String).Trim()
    $datos = $null
    if ($codigo -eq 0 -and $texto) { $datos = ($texto | ConvertFrom-Json).data }
    [pscustomobject]@{ Ok = ($codigo -eq 0); Datos = $datos; Error = $detalle.Trim() }
}

function Exigir($resultado, [string]$que) {
    if (-not $resultado.Ok) { Detener "No se pudo $que.`n$($resultado.Error)" }
    $resultado.Datos
}

# PowerShell 5.1 le quita las comillas al JSON que se pasa a programas externos: va en un archivo (file://).
function Archivo-Json($objeto) {
    $ruta = Join-Path $env:TEMP ('oci-' + [guid]::NewGuid().ToString('N') + '.json')
    $json = ConvertTo-Json -InputObject $objeto -Depth 10 -Compress
    [IO.File]::WriteAllText($ruta, $json, (New-Object Text.UTF8Encoding $false))
    $temporales.Add($ruta)
    "file://$ruta"
}

function Leer-Tenancy {
    $ruta = $env:OCI_CLI_CONFIG_FILE
    if (-not $ruta) { $ruta = Join-Path $HOME '.oci\config' }
    if (-not (Test-Path $ruta)) { Detener "No encuentro $ruta. Configura la API key primero (docs/despliegue.md)." }
    $seccion = $null
    foreach ($linea in Get-Content $ruta) {
        $l = $linea.Trim()
        if ($l -match '^\[(.+)\]$') { $seccion = $Matches[1]; continue }
        if ($seccion -eq $Perfil -and $l -match '^tenancy\s*=\s*(\S+)') { return $Matches[1] }
    }
    Detener "El perfil [$Perfil] de $ruta no tiene 'tenancy'."
}

function Buscar-Instancia([string]$compartimento) {
    $r = Exigir (Invocar-Oci @('compute', 'instance', 'list', '--compartment-id', $compartimento,
            '--display-name', $Nombre, '--all')) 'listar las instancias'
    @($r) | Where-Object { $_ -and $_.'lifecycle-state' -notin @('TERMINATED', 'TERMINATING') } | Select-Object -First 1
}

function Buscar-Imagen([string]$compartimento) {
    $r = Exigir (Invocar-Oci @('compute', 'image', 'list', '--compartment-id', $compartimento,
            '--operating-system', 'Canonical Ubuntu', '--operating-system-version', '24.04', '--shape', $Forma,
            '--sort-by', 'TIMECREATED', '--sort-order', 'DESC', '--limit', '1')) 'buscar la imagen de Ubuntu'
    $imagen = @($r) | Select-Object -First 1
    if (-not $imagen) { Detener 'No hay imagen de Ubuntu 24.04 para ARM en tu región.' }
    $imagen
}

# Lista de seguridad "dragones-web" (80 y 443 desde internet), agregada a la subred sin tocar las que ya tiene.
function Asegurar-PuertosWeb([string]$compartimento, $subred) {
    $r = Exigir (Invocar-Oci @('network', 'security-list', 'list', '--compartment-id', $compartimento,
            '--vcn-id', $subred.'vcn-id', '--display-name', 'dragones-web', '--lifecycle-state', 'AVAILABLE')) `
        'buscar la lista de seguridad web'
    $lista = @($r) | Where-Object { $_ } | Select-Object -First 1
    if (-not $lista) {
        $reglas = foreach ($puerto in 80, 443) {
            @{ protocol = '6'; source = '0.0.0.0/0'; sourceType = 'CIDR_BLOCK'; isStateless = $false
               tcpOptions = @{ destinationPortRange = @{ min = $puerto; max = $puerto } } }
        }
        $lista = Exigir (Invocar-Oci @('network', 'security-list', 'create', '--compartment-id', $compartimento,
                '--vcn-id', $subred.'vcn-id', '--display-name', 'dragones-web',
                '--ingress-security-rules', (Archivo-Json @($reglas)),
                '--egress-security-rules', (Archivo-Json @()), '--wait-for-state', 'AVAILABLE')) `
            'crear la lista de seguridad web'
        Escribir 'Puertos 80 y 443 abiertos (lista de seguridad dragones-web).'
    }
    $actuales = @($subred.'security-list-ids')
    if ($actuales -notcontains $lista.id) {
        $null = Exigir (Invocar-Oci @('network', 'subnet', 'update', '--subnet-id', $subred.id,
                '--security-list-ids', (Archivo-Json @($actuales + $lista.id)), '--force',
                '--wait-for-state', 'AVAILABLE')) 'agregar los puertos web a la subred'
        Escribir 'Lista de seguridad web agregada a la subred.'
    }
}

function Crear-Red([string]$compartimento) {
    Escribir 'No hay subred pública: creo la red dragones-red...'
    $vcn = Exigir (Invocar-Oci @('network', 'vcn', 'create', '--compartment-id', $compartimento,
            '--cidr-block', '10.0.0.0/16', '--display-name', 'dragones-red', '--dns-label', 'dragones',
            '--wait-for-state', 'AVAILABLE')) 'crear la VCN'
    $puerta = Exigir (Invocar-Oci @('network', 'internet-gateway', 'create', '--compartment-id', $compartimento,
            '--vcn-id', $vcn.id, '--is-enabled', 'true', '--display-name', 'dragones-internet',
            '--wait-for-state', 'AVAILABLE')) 'crear el internet gateway'
    $ruta = @(@{ destination = '0.0.0.0/0'; destinationType = 'CIDR_BLOCK'; networkEntityId = $puerta.id })
    $null = Exigir (Invocar-Oci @('network', 'route-table', 'update', '--rt-id', $vcn.'default-route-table-id',
            '--route-rules', (Archivo-Json $ruta), '--force', '--wait-for-state', 'AVAILABLE')) `
        'crear la ruta a internet'
    $subred = Exigir (Invocar-Oci @('network', 'subnet', 'create', '--compartment-id', $compartimento,
            '--vcn-id', $vcn.id, '--cidr-block', '10.0.0.0/24', '--display-name', 'dragones-publica',
            '--dns-label', 'publica', '--wait-for-state', 'AVAILABLE')) 'crear la subred'
    Escribir 'Red creada (la lista de seguridad por defecto ya permite SSH).' 'Green'
    $subred
}

function Obtener-Subred([string]$compartimento) {
    $r = Exigir (Invocar-Oci @('network', 'subnet', 'list', '--compartment-id', $compartimento,
            '--lifecycle-state', 'AVAILABLE', '--all')) 'listar las subredes'
    $subred = @($r) | Where-Object { $_ -and -not $_.'prohibit-public-ip-on-vnic' } | Select-Object -First 1
    if ($subred) { Escribir "Uso la subred pública existente '$($subred.'display-name')'." }
    else { $subred = Crear-Red $compartimento }
    Asegurar-PuertosWeb $compartimento $subred
    $subred
}

function Mostrar-Exito($instancia) {
    if ($instancia.'lifecycle-state' -ne 'RUNNING') {
        Escribir 'La VM existe; espero a que encienda...'
        $instancia = Exigir (Invocar-Oci @('compute', 'instance', 'get', '--instance-id', $instancia.id,
                '--wait-for-state', 'RUNNING', '--max-wait-seconds', '900')) 'esperar a que encienda la VM'
    }
    $vnics = Exigir (Invocar-Oci @('compute', 'instance', 'list-vnics', '--instance-id', $instancia.id)) `
        'leer la IP de la VM'
    $ip = (@($vnics) | Select-Object -First 1).'public-ip'
    foreach ($tono in 660, 880, 1100) { [console]::Beep($tono, 250) }
    Write-Host ''
    Escribir "¡LISTO! La VM '$Nombre' está encendida." 'Green'
    Escribir "IP pública: $ip" 'Green'
    Escribir "Entra con:  ssh ubuntu@$ip" 'Green'
    Escribir 'Sigue con docs/despliegue.md, paso 1.' 'Green'
}

try {
    if (-not (Get-Command oci -ErrorAction SilentlyContinue)) {
        Detener 'No encuentro la CLI de Oracle (oci). Instálala primero (docs/despliegue.md).'
    }
    if (-not (Test-Path $ClavePublica)) { Detener "No encuentro la llave pública SSH: $ClavePublica" }
    if ((Get-Content -Raw $ClavePublica) -notmatch '^(ssh-|ecdsa-)') {
        Detener "$ClavePublica no parece una llave pública (debe empezar por ssh-). ¿Elegiste la privada?"
    }
    if ($MemoriaGb -gt 6 * $Ocpus) { Detener "Con $Ocpus OCPU el máximo es $(6 * $Ocpus) GB de memoria." }

    $tenancy = Leer-Tenancy
    $dominios = @((Exigir (Invocar-Oci @('iam', 'availability-domain', 'list', '--compartment-id', $tenancy)) `
                'conectar con Oracle (revisa la API key)') | ForEach-Object { $_.name })
    Escribir "Conectado. Zonas disponibles: $($dominios -join ', ')" 'Green'

    $existente = Buscar-Instancia $tenancy
    if ($existente) { Mostrar-Exito $existente; exit 0 }

    $imagen = Buscar-Imagen $tenancy
    Escribir "Imagen: $($imagen.'display-name')"
    $subred = Obtener-Subred $tenancy
    if ($subred.'availability-domain') { $dominios = @($subred.'availability-domain') }  # subred atada a una zona

    $configForma = Archivo-Json @{ ocpus = $Ocpus; memoryInGBs = $MemoriaGb }
    Escribir "Pidiendo $Forma ($Ocpus OCPU, $MemoriaGb GB, disco $DiscoGb GB) cada $EsperaSegundos s. Ctrl+C para parar." 'Cyan'
    Escribir 'Deja el PC encendido y sin suspender. Puede tardar horas o días.' 'Cyan'

    $intento = 0
    while ($true) {
        foreach ($zona in $dominios) {
            $intento++
            # Por si un intento anterior sí creó la VM aunque la respuesta se perdiera.
            $existente = Buscar-Instancia $tenancy
            if ($existente) { Mostrar-Exito $existente; exit 0 }

            $r = Invocar-Oci @('compute', 'instance', 'launch', '--availability-domain', $zona,
                '--compartment-id', $tenancy, '--shape', $Forma, '--shape-config', $configForma,
                '--image-id', $imagen.id, '--subnet-id', $subred.id, '--assign-public-ip', 'true',
                '--display-name', $Nombre, '--ssh-authorized-keys-file', $ClavePublica,
                '--boot-volume-size-in-gbs', "$DiscoGb",
                '--wait-for-state', 'RUNNING', '--max-wait-seconds', '900')
            if ($r.Ok) { Mostrar-Exito $r.Datos; exit 0 }

            $espera = $EsperaSegundos
            if ($r.Error -match 'capacity') {
                Escribir "Intento $intento en $($zona.Split(':')[-1]): sin cupo."
            } elseif ($r.Error -match 'TooManyRequests') {
                Escribir "Intento ${intento}: Oracle pide ir más despacio; espero el triple." 'Yellow'
                $espera = 3 * $EsperaSegundos
            } elseif ($r.Error -match 'LimitExceeded|QuotaExceeded') {
                Detener "Tu cuenta ya usa su cupo gratuito de ARM (¿otra VM encendida?).`n$($r.Error)"
            } elseif ($r.Error -match 'NotAuthenticated|NotAuthorized|InvalidParameter|CannotParseRequest') {
                Detener "Oracle rechazó la petición; reintentar no lo arregla.`n$($r.Error)"
            } else {
                $ultimas = ($r.Error -split "`n" | Select-Object -Last 3) -join ' '
                Escribir "Intento ${intento}: error temporal, sigo intentando. $ultimas" 'Yellow'
            }
            Start-Sleep -Seconds $espera
        }
    }
} finally {
    foreach ($ruta in $temporales) { Remove-Item $ruta -ErrorAction SilentlyContinue }
}
