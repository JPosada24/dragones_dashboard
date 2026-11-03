# Reintenta crear la VM gratuita de Oracle Cloud (VM.Standard.A1.Flex) hasta que haya cupo.
#
# Traducción de deploy/oracle/conseguir-vm.ps1 a Python + SDK de OCI, para que el mismo reintent
# automático corra también en GitHub Actions (ver .github/workflows/conseguir-vm.yml), donde la
# CLI de oci no está pero el SDK basta. Guía completa: docs/despliegue.md, sección "Oracle Cloud gratis".
#
# Oracle responde "Out of host capacity" cuando no quedan máquinas ARM gratuitas en la zona: este
# programa insiste rotando por las zonas (availability domains) del home region hasta que una acepte.
# Es idempotente: si la VM ya existe, solo informa su IP (y en Actions la marca en outputs).
#
# Local:   python deploy/oracle/conseguir-vm.py                      (usa ~/.oci/config, como la CLI)
# Actions: exporta OCI_CLI_USER, OCI_CLI_TENANCY, OCI_CLI_FINGERPRINT, OCI_CLI_KEY_CONTENT,
#          OCI_CLI_REGION y SSH_PUB_KEY (los secretos del workflow). Sino, termina con exit 2.

from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
import time
import urllib.request
from typing import Any, Callable

import oci
from oci.core.models import (
    CreateInternetGatewayDetails,
    CreateSecurityListDetails,
    CreateSubnetDetails,
    CreateVcnDetails,
    CreateVnicDetails,
    IngressSecurityRule,
    InstanceSourceViaImageDetails,
    LaunchInstanceDetails,
    LaunchInstanceShapeConfigDetails,
    PortRange,
    RouteRule,
    TcpOptions,
    UpdateRouteTableDetails,
    UpdateSubnetDetails,
)

FORMA = "VM.Standard.A1.Flex"
NOMBRE_LISTA_WEB = "dragones-web"


def escribir(texto: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {texto}", flush=True)


def detener(texto: str, codigo: int = 2) -> "NoReturn":  # type: ignore[misc]
    escribir(f"PARO: {texto}")
    resumen(title="Resultado: parado por un error que ni reintentando se arregla", fragmentos=[texto])
    sys.exit(codigo)


def set_output(nombre: str, valor: str) -> None:
    ruta = os.getenv("GITHUB_OUTPUT")
    if ruta:
        with open(ruta, "a", encoding="utf-8") as archivo:
            archivo.write(f"{nombre}={valor}\n")


def resumen(title: str, fragmentos: list[str] | None = None) -> None:
    """Escribe en el resumen del run de Actions ($GITHUB_STEP_SUMMARY), si existe."""
    ruta = os.getenv("GITHUB_STEP_SUMMARY")
    if not ruta:
        return
    lineas = [f"## {title}", ""]
    lineas += (fragmentos or [])
    with open(ruta, "a", encoding="utf-8") as archivo:
        archivo.write("\n".join(lineas) + "\n")


def avisar_telegram(texto: str) -> None:
    """Aviso opcional (secretos TELEGRAM_*): si falla o no están, la ejecución sigue igual."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return
    try:
        peticion = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=json.dumps({"chat_id": chat, "text": texto}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(peticion, timeout=15):
            escribir("Aviso de Telegram enviado.")
    except Exception as error:  # noqa: BLE001 - bajo ningún motivo bloquea el éxito
        escribir(f"El aviso por Telegram falló (no importa): {error}")


# ------- Configuración del SDK: secretos (Actions) o ~/.oci/config (local) -------

def cargar_config() -> dict[str, str]:
    if os.getenv("OCI_CLI_KEY_CONTENT"):
        faltantes = [v for v in ("OCI_CLI_USER", "OCI_CLI_TENANCY", "OCI_CLI_REGION", "OCI_CLI_FINGERPRINT")
                     if not os.getenv(v)]
        if faltantes:
            detener(f"Secretos sin definir: {', '.join(faltantes)}")
        config = {
            "user": os.environ["OCI_CLI_USER"],
            "tenancy": os.environ["OCI_CLI_TENANCY"],
            "region": os.environ["OCI_CLI_REGION"],
            "fingerprint": os.environ["OCI_CLI_FINGERPRINT"],
            "key_content": os.environ["OCI_CLI_KEY_CONTENT"],
        }
    else:
        config = oci.config.from_file(profile=os.getenv("OCI_CLI_PROFILE", "DEFAULT"))
    return config


def cargar_llave_publica() -> str:
    raw = os.getenv("SSH_PUB_KEY")
    if raw:
        contenido = raw.strip()
    else:
        ruta = os.path.expanduser("~/.ssh/id_ed25519.pub")
        if not os.path.exists(ruta):
            detener(f"No encuentro la llave pública SSH: {ruta}")
        with open(ruta, encoding="utf-8") as archivo:
            contenido = archivo.read().strip()
    if not (contenido.startswith("ssh-") or contenido.startswith("ecdsa-")):
        detener("No parece una llave pública (debe empezar por ssh-). ¿Copiaste la privada?")
    return contenido


# ------- Lógica idéntica al .ps1 -------

def buscar_instancia(compute: oci.core.ComputeClient, compartimento: str, nombre: str) -> Any | None:
    instancias = compute.list_instances(compartment_id=compartimento, display_name=nombre).data
    vivas = [i for i in instancias if i.lifecycle_state not in ("TERMINATED", "TERMINATING")]
    return vivas[0] if vivas else None


def buscar_imagen(compute: oci.core.ComputeClient, compartimento: str) -> Any:
    respuesta = compute.list_images(
        compartment_id=compartimento,
        operating_system="Canonical Ubuntu",
        operating_system_version="24.04",
        shape=FORMA,
        sort_by="TIMECREATED",
        sort_order="DESC",
        limit=1,
    )
    if not respuesta.data:
        detener(f"No hay imagen de Ubuntu 24.04 para {FORMA} en tu región.")
    return respuesta.data[0]


def esperar(getter: Callable[[], Any], atributo: str, objetivo: str, tope: int = 300) -> Any:
    """Equivale a --wait-for-state: sondea cada 5 s hasta el estado (o devuelve el último valor)."""
    recurso = getter()
    por_tocar = time.monotonic() + tope
    while getattr(recurso, atributo) != objetivo and time.monotonic() < por_tocar:
        time.sleep(5)
        recurso = getter()
    return recurso


def crear_red(network: oci.core.VirtualNetworkClient, compartimento: str) -> Any:
    escribir("No hay subred pública: creo la red dragones-red...")
    vcn = network.create_vcn(
        CreateVcnDetails(
            compartment_id=compartimento,
            display_name="dragones-red",
            dns_label="dragones",
            cidr_blocks=["10.0.0.0/16"],
        )
    ).data
    esperar(lambda: network.get_vcn(vcn.id).data, "lifecycle_state", "AVAILABLE")

    puerta = network.create_internet_gateway(
        CreateInternetGatewayDetails(
            compartment_id=compartimento,
            vcn_id=vcn.id,
            is_enabled=True,
            display_name="dragones-internet",
        )
    ).data
    esperar(lambda: network.get_internet_gateway(puerta.id).data, "lifecycle_state", "AVAILABLE")

    network.update_route_table(
        rt_id=vcn.default_route_table_id,
        update_route_table_details=UpdateRouteTableDetails(
            route_rules=[
                RouteRule(destination="0.0.0.0/0", destination_type="CIDR_BLOCK", network_entity_id=puerta.id)
            ]
        ),
    )
    esperar(lambda: network.get_route_table(vcn.default_route_table_id).data, "lifecycle_state", "AVAILABLE")

    subred = network.create_subnet(
        CreateSubnetDetails(
            compartment_id=compartimento,
            vcn_id=vcn.id,
            cidr_block="10.0.0.0/24",
            display_name="dragones-publica",
            dns_label="publica",
        )
    ).data
    esperar(lambda: network.get_subnet(subred.id).data, "lifecycle_state", "AVAILABLE")
    escribir("Red creada (la lista de seguridad por defecto ya permite SSH).")
    return subred


def asegurar_puertos_web(network: oci.core.VirtualNetworkClient, compartimento: str, subred: Any) -> None:
    respuesta = network.list_security_lists(
        compartment_id=compartimento,
        vcn_id=subred.vcn_id,
        display_name=NOMBRE_LISTA_WEB,
        lifecycle_state="AVAILABLE",
    ).data
    lista = respuesta[0] if respuesta else None
    if lista is None:
        lista = network.create_security_list(
            CreateSecurityListDetails(
                compartment_id=compartimento,
                vcn_id=subred.vcn_id,
                display_name=NOMBRE_LISTA_WEB,
                ingress_security_rules=[
                    IngressSecurityRule(
                        protocol="6",
                        source="0.0.0.0/0",
                        source_type="CIDR_BLOCK",
                        is_stateless=False,
                        tcp_options=TcpOptions(destination_port_range=PortRange(min=puerto, max=puerto)),
                    )
                    for puerto in (80, 443)
                ],
                egress_security_rules=[],
            )
        ).data
        esperar(lambda: network.get_security_list(lista.id).data, "lifecycle_state", "AVAILABLE")
        escribir("Puertos 80 y 443 abiertos (lista de seguridad dragones-web).")
    actuales = list(subred.security_list_ids)
    if lista.id not in actuales:
        network.update_subnet(
            subnet_id=subred.id,
            update_subnet_details=UpdateSubnetDetails(security_list_ids=actuales + [lista.id]),
        )
        esperar(lambda: network.get_subnet(subred.id).data, "lifecycle_state", "AVAILABLE")
        escribir("Lista de seguridad web agregada a la subred.")


def obtener_subred(network: oci.core.VirtualNetworkClient, compartimento: str) -> Any:
    subredes = [
        s
        for s in network.list_subnets(compartment_id=compartimento, lifecycle_state="AVAILABLE").data
        if not s.prohibit_public_ip_on_vnic
    ]
    if subredes:
        subred = subredes[0]
        escribir(f"Uso la subred pública existente '{subred.display_name}'.")
    else:
        subred = crear_red(network, compartimento)
    asegurar_puertos_web(network, compartimento, subred)
    return subred


def clasificar_error(error: Exception) -> str:
    """Same criteria as .ps1: what decides whether to insist (capacity/pace) or stop."""
    if not isinstance(error, oci.exceptions.ServiceError):
        return "paso"  # red y otros: reintentar
    codigo = error.code or ""
    texto = f"{codigo} {error.message or ''}".lower()
    if "capacity" in texto:
        return "capacity"
    if error.status == 429 or "toomanyrequests" in texto:
        return "paced"
    if "limitexceeded" in texto or "quotaexceeded" in texto:
        return "quota"
    if codigo in {"NotAuthenticated", "NotAuthorized", "InvalidParameter", "CannotParseRequest"}:
        return "fatal"
    return "paso"


def reportar_exito(
    compute: oci.core.ComputeClient,
    instancia: Any,
    config_forma: dict[str, int],
    zona: str | None,
) -> None:
    if instancia.lifecycle_state != "RUNNING":
        escribir("La VM existe; espero a que encienda (hasta 5 min)...")
        instancia = esperar(
            lambda: compute.get_instance(instancia.id).data, "lifecycle_state", "RUNNING", tope=300
        )

    vnics = compute.list_vnics(instance_id=instancia.id).data
    ip = (vnics[0].public_ip if vnics else None) or ""

    if instancia.lifecycle_state == "RUNNING" and ip:
        set_output("vm_listed", "true")
        set_output("ip", ip)
        avisar_telegram(
            f"Dragones: la VM de Oracle ya encendió. IP: {ip}\nEntra con: ssh ubuntu@{ip}"
            "\nSigue con docs/despliegue.md."
        )
        resumen(
            title="VM Oracle gratuita creada",
            fragmentos=[
                f"**IP pública:** `{ip}`",
                f"**Acceso:** `ssh ubuntu@{ip}`",
                f"**Forma:** {FORMA} ({config_forma['ocpus']} OCPU, {config_forma['memoryInGBs']} GB)",
                f"**Zona:** {zona or '(regional)'}",
                "",
                "Sigue con **docs/despliegue.md, paso 1.3** en adelante (usuario, puertos, Docker).",
                "Cuando la uses, puedes apagar este workflow (Actions → Conseguir VM Oracle → Disable).",
            ],
        )
        escribir("=" * 60)
        escribir(f"LISTO. La VM '{instancia.display_name}' está encendida.")
        escribir(f"IP pública: {ip}")
        escribir(f"Entra con:  ssh ubuntu@{ip}")
        escribir("Sigue con docs/despliegue.md.")
        escribir("=" * 60)
    else:
        # Excepcional (no llegó a RUNNING en el tope o aún no tiene IP): la siguiente
        # ejecución entra por el "busca-instancia" y aquí mismo termina de reportarla.
        escribir("La VM no tiene IP útil todavía; la próxima ejecución informará la IP.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Insiste creando la VM gratuita de Oracle (A1.Flex) hasta que haya cupo."
    )
    parser.add_argument("--instance-name", default="dragones")
    parser.add_argument("--ocpus", type=int, default=2)
    parser.add_argument("--memory-gb", type=int, default=12)
    parser.add_argument("--disk-gb", type=int, default=100)
    parser.add_argument(
        "--wait-seconds", type=int, default=60, help="pausa entre intentos (en Actions basta 15)"
    )
    parser.add_argument(
        "--attempts", type=int, default=0, help="intentos máximos por ejecución; 0 es sin límite (local)"
    )
    args = parser.parse_args()

    if not 1 <= args.ocpus <= 4:
        detener("--ocpus debe ser 1..4 (el free tier regala 4 en total).")
    if args.memory_gb > 6 * args.ocpus:
        detener(f"Con {args.ocpus} OCPU el máximo es {6 * args.ocpus} GB de memoria.")
    if not 50 <= args.disk_gb <= 200:
        detener("--disk-gb debe ser 50..200 (el free tier regala 200 GB en total).")

    config = cargar_config()
    llave = cargar_llave_publica()
    tenancy = config["tenancy"]

    identity = oci.identity.IdentityClient(config)
    compute = oci.core.ComputeClient(config)
    network = oci.core.VirtualNetworkClient(config)

    dominios = [d.name for d in identity.list_availability_domains(compartment_id=tenancy).data]
    escribir(f"Conectado ({config['region']}). Zonas: {', '.join(d.split(':')[-1] for d in dominios)}")

    existente = buscar_instancia(compute, tenancy, args.instance_name)
    if existente:
        reportar_exito(compute, existente, {"ocpus": args.ocpus, "memoryInGBs": args.memory_gb}, None)
        return

    imagen = buscar_imagen(compute, tenancy)
    escribir(f"Imagen: {imagen.display_name}")
    subred = obtener_subred(network, tenancy)
    dominios_efectivos = [subred.availability_domain] if subred.availability_domain else dominios

    config_forma = {"ocpus": args.ocpus, "memoryInGBs": args.memory_gb}
    escribir(
        f"Pidiendo {FORMA} ({args.ocpus} OCPU, {args.memory_gb} GB, disco {args.disk_gb} GB) "
        f"cada {args.wait_seconds} s."
    )

    intento = 0
    for zona in itertools.cycle(dominios_efectivos):
        intento += 1
        existente = buscar_instancia(compute, tenancy, args.instance_name)
        if existente:
            escribir("La VM ya existe aunque la respuesta se había perdido: la reporto.")
            reportar_exito(compute, existente, config_forma, zona)
            return

        try:
            lanzada = compute.launch_instance(
                LaunchInstanceDetails(
                    availability_domain=zona,
                    compartment_id=tenancy,
                    display_name=args.instance_name,
                    shape=FORMA,
                    shape_config=LaunchInstanceShapeConfigDetails(
                        ocpu_count=args.ocpus, memory_in_gbs=args.memory_gb
                    ),
                    source_details=InstanceSourceViaImageDetails(
                        image_id=imagen.id, boot_volume_size_in_gbs=args.disk_gb
                    ),
                    create_vnic_details=CreateVnicDetails(
                        subnet_id=subred.id, assign_public_ip=True, display_name="publica"
                    ),
                    metadata={"ssh_authorized_keys": llave},
                )
            ).data
            reportar_exito(compute, lanzada, config_forma, zona)
            return
        except Exception as error:  # noqa: BLE001 - cada falla se clasifica abajo
            clase = clasificar_error(error)
            if clase == "capacity":
                escribir(f"Intento {intento} en {zona.split(':')[-1]}: sin cupo.")
            elif clase == "paced":
                escribir(f"Intento {intento}: Oracle pide ir más despacio; espero el triple.")
                time.sleep(3 * args.wait_seconds)
                continue
            elif clase == "quota":
                detener(
                    "Tu cuenta ya usa su cupo gratuito de ARM (¿otra VM encendida?)\n"
                    f"{getattr(error, 'code', '')} {error}"
                )
            elif clase == "fatal":
                detener(
                    "Oracle rechazó la petición; reintentar no lo arregla (¿secretos del workflow?)\n"
                    f"{getattr(error, 'code', '')} {error}"
                )
            else:
                escribir(f"Intento {intento}: error temporal ({type(error).__name__}); sigo intentando.")

        if args.attempts and intento >= args.attempts:
            resumen(
                title="Resultado: sin cupo en esta ronda (normal)",
                fragmentos=[
                    f"Intentos hechos: {intento}. Sin cupo de ARM todavía.",
                    "La siguiente ejecución programada lo reintentará, no hay que hacer nada.",
                ],
            )
            escribir("Sin cupo en esta ronda; la próxima ejecución lo reintentará.")
            return
        time.sleep(args.wait_seconds)


if __name__ == "__main__":
    main()
