import json
import logging
import traceback
import uuid
import os
import requests

from __init__ import __version__
from fastapi import FastAPI, Request
from fastapi.responses import Response, JSONResponse, PlainTextResponse
from commons.utils import (
    get_from_dict,
    check_vm_tolerance,
    check_vm_params
)
from commons.billing import (
    add_billing_details,
    update_billing_details,
    get_pricing,
)
from models.ComputeModel import (
    ElementoMachine,
    ElementoCpu,
    ElementoMisc,
    ElementoAuth,
    ElementoMemory,
    ElementoPciDev,
)
from models.StorageModel import ElementoStorage
from infrastructure.compute.compute_manager import (
    get_status,
    retrieve_machine_config,
    list_running,
    is_config_available,
    create_compute_machine,
    destroy_server,
    start_server,
    stop_server,
    restart_server,
    get_servers_metrics,
)
from errors.server_errors import (
    ElementoBillingFailed,
    ElementoCreationFailed,
    ElementoInternalServerError,
)
from errors.client_errors import (
    ElementoBadRequest,
    ElementoNotFound,
    BadRequestFieldError,
    ElementoTooEarly,
)

app = FastAPI(docs_url=None)


@app.get("/")
def health():
    return PlainTextResponse(
        status_code=200,
        content=f"Hello, world! This is an Elemento Compute Meson for provider {os.getenv("PROVIDER")}",
    )


@app.get("/api/v1.0/health")
def health():
    return JSONResponse(
        status_code=200,
        content={"status": "UP", "version": __version__},
    )


@app.get("/api/v1.0/status")
def status(req: Request):
    try:
        content_type = req.headers.get("Content-Type")
        vm_list_response = {"vms": []}

        running_machines = get_status()
        if len(running_machines) == 0:
            logging.error("No machine found")
            return Response(status_code=204)

        for machine in running_machines:
            vm_list_response["vms"].append(machine.to_json_status())

        if content_type == "text/plain":
            return PlainTextResponse(
                vm_list_response.__str__(),
                status_code=200,
            )

        return JSONResponse(
            content=vm_list_response,
            status_code=200,
        )

    except Exception as error:
        logging.error(error.__str__())
        return ElementoInternalServerError(
            origin="MESON",
            error=f"Internal Server Error - {error.__str__()}",
            trace=traceback.format_exc(),
            meson_source="status()"
        )


@app.get("/api/v1.0/running/{vm_uuid}")
async def server_description_by_id(req: Request, vm_uuid: str):
    try:
        service_country = req.headers["service_country"] if "service_country" in req.headers.keys() else os.getenv("PROVIDER_REGION")
        machine_config = retrieve_machine_config(machine_id=vm_uuid, service_country=service_country)

        price = get_pricing(machine_config.to_json())
        return JSONResponse(
            status_code=200, content=machine_config.to_json_running(price=price)
        )

    except Exception as error:
        logging.error(error.__str__())
        return ElementoInternalServerError(
            origin="MESON",
            error=f"Internal Server Error - {error.__str__()}",
            meson_source="server_description_by_id()",
            trace=traceback.format_exc()
        )


@app.get("/api/v1.0/running")
async def servers_description(req: Request):
    try:
        service_country = req.headers["service_country"] if "service_country" in req.headers.keys() else os.getenv("PROVIDER_REGION")
        try:
            client_uuid = req.query_params.get("client_uuid")
        except Exception as error:
            return ElementoBadRequest(
                origin="MESON",
                error="Bad Request",
                field_errors=[
                    BadRequestFieldError(
                        field="client_uuid",
                        where="BODY",
                        error="MISSING",
                        type="UUID",
                        expected_value=""
                    )
                ],
                docs_url="",
                trace=traceback.format_exc(),
                meson_source="servers_description()"
            )

        vm_list_response = {"vms": []}
        running_machines = list_running(client_uuid=client_uuid, service_country=service_country)

        if len(running_machines) == 0:
            logging.error("No machine found")
            return Response(status_code=204)

        for machine in running_machines:
            price = get_pricing(machine.to_json())
            vm_list_response["vms"].append(machine.to_json_running(price=price))

        return JSONResponse(status_code=200, content=vm_list_response)

    except Exception as error:
        logging.error(error.__str__())
        return ElementoInternalServerError(
            origin="MESON",
            error=f"Internal Server Error - {error.__str__()}",
            trace=traceback.format_exc(),
            meson_source="servers_description()"
        )


@app.post("/api/v1.0/register")
async def server_creation(req: Request):
    try:
        servers_to_create = await req.json()
        async_flag = "false"
        if req.headers.get("Async") is not None:
            async_flag = req.headers.get("Async")
        service_country = req.headers["service-country"] if "service-country" in req.headers.keys() else os.getenv("PROVIDER_REGION")

        # SETUP OF ELEMENTO MACHINE
        try:
            req_data = (
                get_from_dict(servers_to_create, "req")
                if type(servers_to_create["req"]) is dict
                else json.loads(get_from_dict(servers_to_create, "req"))
            )
            client_uuid = get_from_dict(servers_to_create, "client_uuid")
            vm_name = get_from_dict(servers_to_create, "vm_name")

            if req_data.get("pci") is not None:
                pci_devices = get_from_dict(req_data, "pci", "devices")
                elemento_pci_devices = []
                for key in pci_devices:
                    pci_vendor, pci_model = key.split(":")
                    pci_quantity = get_from_dict(pci_devices, key)
                    elemento_pci_devices.append(
                        ElementoPciDev(
                            vendor=pci_vendor,
                            model=pci_model,
                            quantity=pci_quantity,
                        )
                    )
            else:
                elemento_pci_devices = None

            if servers_to_create.get("volumes") != [] and servers_to_create.get("volumes") is not None:
                volumes_to_attach = get_from_dict(servers_to_create, "volumes")
                elemento_volumes = []
                for volume in volumes_to_attach:
                    elemento_volumes.append(
                        ElementoStorage(
                            creator_id=client_uuid,
                            csp_region=service_country,
                            volume_uuid=volume.get("volume_uuid"),
                            name=get_from_dict(volume, "name"),
                            private=volume.get("private"),
                            readonly=volume.get("readonly"),
                            shareable=volume.get("shareable"),
                            bootable=volume.get("bootable"),
                            size=get_from_dict(volume, "size"),
                        )
                    )
            elif servers_to_create.get("volume") is not None:
                volumes_to_attach = get_from_dict(servers_to_create, "volumes")
                elemento_volumes = []
                for volume in volumes_to_attach:
                    elemento_volumes.append(
                        ElementoStorage(
                            creator_id=client_uuid,
                            csp_region=service_country,
                            volume_uuid=volume.get("volume_uuid"),
                            name=get_from_dict(volume, "name"),
                            private=volume.get("private"),
                            readonly=volume.get("readonly"),
                            shareable=volume.get("shareable"),
                            bootable=volume.get("bootable"),
                            size=get_from_dict(volume, "size"),
                        )
                    )
            else:
                elemento_volumes = None

            vm_data = ElementoMachine(
                csp_region=service_country,
                client_uuid=client_uuid,
                vm_name=vm_name,
                volumes=elemento_volumes,
                cpu=ElementoCpu(
                    slots=get_from_dict(req_data, "cpu", "slots"),
                    fullPhysical=(
                        get_from_dict(req_data, "cpu").get("fullPhysical")
                        if get_from_dict(req_data, "cpu").get("fullPhysical")
                        is not None
                        else False  # default value
                    ),
                    maxOverprovision=(
                        get_from_dict(req_data, "cpu").get("maxOverprovision")
                        if get_from_dict(req_data, "cpu").get("maxOverprovision")
                        is not None
                        else 1  # default value
                    ),
                    min_frequency=get_from_dict(req_data, "cpu", "min_frequency"),
                    arch=get_from_dict(req_data, "cpu", "arch"),
                    flags=get_from_dict(req_data, "cpu", "flags"),
                ),
                mem=ElementoMemory(
                    capacity=get_from_dict(req_data, "mem", "capacity"),
                    requireECC=get_from_dict(req_data, "mem").get("reqECC"),
                ),
                pci=elemento_pci_devices,
                misc=ElementoMisc(
                    os_family=get_from_dict(req_data, "misc", "os_family"),
                    os_flavour=get_from_dict(req_data, "misc", "os_flavour"),
                ),
                network_config=None,
                auth=ElementoAuth(
                    username=get_from_dict(servers_to_create, "authentication").get("username"),
                    password=get_from_dict(servers_to_create, "authentication").get("password"),
                    ssh_key=get_from_dict(servers_to_create, "authentication").get("ssh-key"),
                ),
            )
        except Exception as error:
            return ElementoBadRequest(
                origin="MESON",
                error="Bad Request - bad payload",
                field_errors=[],
                docs_url="",
                trace=traceback.format_exc(),
                meson_source="server_creation()"
            )

        # CREATE MACHINE
        try:
            vm_uuid = create_compute_machine(vm_data, service_country)
            return JSONResponse(
                content={
                    "vm_uuid": vm_uuid,
                    "poolingURL": f"https://api/v1.0/running/{vm_uuid}",
                },
                status_code=202,
            )
        except Exception as error:
            # update_billing_details(billing_uuid, "ended")
            return ElementoCreationFailed(
                origin="MESON",
                error="Error during actual creation",
                trace=traceback.format_exc(),
                stopped_successfully=True,
                billing_suspended=True,
                meson_source="server_creation()"
            )

        created_machine.creation_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return JSONResponse(content=created_machine.to_json_register(), status_code=200)

    except Exception as error:
        logging.error(error.__str__())
        return ElementoInternalServerError(
            origin="MESON",
            error=f"Internal Server Error - {error.__str__()}",
            trace=traceback.format_exc(),
            meson_source="server_creation()"
        )


@app.get("/api/v1.0/canallocate")
async def cancreate(req: Request):
    try:
        servers_to_create = await req.json()
        service_country = req.headers["service-country"] if "service-country" in req.headers.keys() else os.getenv("PROVIDER_REGION")

        # SETUP OF ELEMENTO MACHINE
        try:
            req_data = (
                get_from_dict(servers_to_create, "req")
                if type(servers_to_create["req"]) is dict
                else json.loads(get_from_dict(servers_to_create, "req"))
            )
            client_uuid = get_from_dict(servers_to_create, "client_uuid")

            if req_data.get("pci") is not None:
                pci_devices = get_from_dict(req_data, "pci", "devices")
                elemento_pci_devices = []
                for key in pci_devices:
                    pci_vendor, pci_model = key.split(":")
                    pci_quantity = get_from_dict(pci_devices, key)
                    elemento_pci_devices.append(
                        ElementoPciDev(
                            vendor=pci_vendor,
                            model=pci_model,
                            quantity=pci_quantity,
                        )
                    )
            else:
                elemento_pci_devices = None

            if servers_to_create.get("volumes") is not None:
                volumes_to_attach = get_from_dict(servers_to_create, "volumes")
                elemento_volumes = []
                for volume in volumes_to_attach:
                    elemento_volumes.append(
                        ElementoStorage(
                            csp_region=service_country,
                            volume_uuid=volume.get("volume_uuid"),
                            name=get_from_dict(volume, "name"),
                            private=volume.get("private"),
                            readonly=volume.get("readonly"),
                            shareable=volume.get("shareable"),
                            bootable=volume.get("bootable"),
                            size=get_from_dict(volume, "size"),
                        )
                    )
            if servers_to_create.get("volume") is not None:
                volumes_to_attach = get_from_dict(servers_to_create, "volumes")
                elemento_volumes = []
                for volume in volumes_to_attach:
                    elemento_volumes.append(
                        ElementoStorage(
                            creator_id=client_uuid,
                            csp_region=service_country,
                            volume_uuid=volume.get("volume_uuid"),
                            name=get_from_dict(volume, "name"),
                            private=volume.get("private"),
                            readonly=volume.get("readonly"),
                            shareable=volume.get("shareable"),
                            bootable=volume.get("bootable"),
                            size=get_from_dict(volume, "size"),
                        )
                    )
            else:
                elemento_volumes = None

            vm_data = ElementoMachine(
                csp_region=service_country,
                volumes=elemento_volumes,
                cpu=ElementoCpu(
                    slots=get_from_dict(req_data, "cpu", "slots"),
                    fullPhysical=(
                        get_from_dict(req_data, "cpu").get("fullPhysical")
                        if get_from_dict(req_data, "cpu").get("fullPhysical")
                        is not None
                        else False  # default value
                    ),
                    maxOverprovision=(
                        get_from_dict(req_data, "cpu").get("maxOverprovision")
                        if get_from_dict(req_data, "cpu").get("maxOverprovision")
                        is not None
                        else 1  # default value
                    ),
                    min_frequency=get_from_dict(req_data, "cpu", "min_frequency"),
                    arch=get_from_dict(req_data, "cpu", "arch"),
                    flags=get_from_dict(req_data, "cpu", "flags"),
                ),
                mem=ElementoMemory(
                    capacity=get_from_dict(req_data, "mem", "capacity"),
                    requireECC=get_from_dict(req_data, "mem").get("requireECC"),
                ),
                pci=elemento_pci_devices,
                misc=ElementoMisc(
                    os_family=get_from_dict(req_data, "misc").get("os_family"),
                    os_flavour=get_from_dict(req_data, "misc").get("os_flavour"),
                ),
                network_config=None,
                auth=ElementoAuth(
                    username=get_from_dict(servers_to_create, "authentication").get("username"),
                    password=get_from_dict(servers_to_create, "authentication").get("password"),
                    ssh_key=get_from_dict(servers_to_create, "authentication").get("ssh-key"),
                ),
            )
        except Exception as error:
            return ElementoBadRequest(
                origin="MESON",
                error="Bad Request - bad payload",
                field_errors=[],
                docs_url="",
                trace=traceback.format_exc(),
                meson_source="cancreate()"
            )

        # CHECK CONFIGURATION
        vm_config = is_config_available(vm_data, service_country)
        if vm_config is None or not check_vm_tolerance(
            requested=vm_data, proposed=vm_config
        ):
            return ElementoCreationFailed(
                origin="MESON",
                error="Config is not available",
                trace=traceback.format_exc(),
                stopped_successfully=True,
                billing_suspended=True,
                meson_source="cancreate()",
            )

        # GET PRICING
        price = get_pricing(vm_config.to_json())
        if price is None:
            return ElementoCreationFailed(
                origin="MESON",
                error="Price is not available",
                trace=traceback.format_exc(),
                stopped_successfully=True,
                billing_suspended=True,
                meson_source="cancreate()",
            )

        return JSONResponse(
            status_code=200,
            content={
                "config": vm_config.to_json(),
                "info": vm_config.to_json_canallocate(price=price),
            },
        )

    except Exception as error:
        logging.error(error.__str__())
        return ElementoInternalServerError(
            origin="MESON",
            error=f"Internal Server Error - {error.__str__()}",
            trace=traceback.format_exc(),
            meson_source="cancreate()"
        )


@app.delete("/api/v1.0/unregister")
async def server_destruction(req: Request):
    try:
        to_destroy = await req.json()
        service_country = req.headers["service_country"] if "service_country" in req.headers.keys() else os.getenv("PROVIDER_REGION")

        try:
            vm_uuid = get_from_dict(to_destroy, "vm_uuid")
        except Exception as error:
            return ElementoBadRequest(
                origin="MESON",
                error="Bad Request",
                field_errors=[
                    BadRequestFieldError(
                        field="vm_uuid",
                        where="BODY",
                        error="MISSING",
                        type="UUID",
                        expected_value=""
                    )
                ],
                docs_url="",
                trace=traceback.format_exc(),
                meson_source="server_destruction()"
            )
        try:
            client_uuid = get_from_dict(to_destroy, "client_uuid")
        except Exception as error:
            return ElementoBadRequest(
                origin="MESON",
                error="Bad Request",
                field_errors=[
                    BadRequestFieldError(
                        field="client_uuid",
                        where="BODY",
                        error="MISSING",
                        type="UUID",
                        expected_value=""
                    )
                ],
                docs_url="",
                trace=traceback.format_exc(),
                meson_source="server_destruction()"
            )

        try:
            machine_config = retrieve_machine_config(vm_uuid, service_country)
        except Exception as error:
            return ElementoNotFound(
                origin="MESON",
                error="Error retrieving machine config",
                trace=traceback.format_exc(),
                meson_source="server_destruction()"
            )

        try:
            response = destroy_server(client_uuid, vm_uuid, service_country)
        except Exception as error:
            return ElementoInternalServerError(
                origin="MESON",
                error="Error during server destruction",
                trace=traceback.format_exc(),
                meson_source="server_destruction()"
            )

        try:
            print("Billing stop")
            # update_billing_details(machine_config.billing_uuid, status="STOP")
        except Exception as error:
            return ElementoBillingFailed(
                origin="MESON",
                error="Error during billing suspension",
                trace=traceback.format_exc(),
                meson_source="server_destruction()"
            )

        return JSONResponse(
            status_code=200, content={"unregistered": response, "uniqueID": vm_uuid}
        )

    except Exception as error:
        logging.error(error.__str__())
        return ElementoInternalServerError(
            origin="MESON",
            error=f"Internal Server Error - {error.__str__()}",
            trace=traceback.format_exc(),
            meson_source="server_destruction()"
        )


@app.post("/api/v1.0/start")
async def server_start(req: Request):
    try:
        to_start = await req.json()
        service_country = req.headers["service_country"] if "service_country" in req.headers.keys() else os.getenv("PROVIDER_REGION")
        vm_uuid = get_from_dict(to_start, "vm_uuid")
        client_uuid = get_from_dict(to_start, "client_uuid")

        try:
            start_server(client_uuid, vm_uuid, service_country)
        except Exception as error:
            logging.error("server_start -", error.__str__())
            return ElementoNotFound(
                origin="MESON",
                error=f"Not found - {error.__str__()}",
                trace=traceback.format_exc(),
                meson_source="server_start()"
            )

        return JSONResponse(
            status_code=202,
            content={"success": f"Starting VM {vm_uuid}"}
        )

    except requests.HTTPError as http_err:
        logging.error("server_start -", http_err.__str__())
        return ElementoTooEarly(
            origin="MESON",
            error=f"Too early - {http_err.__str__()}",
            trace=traceback.format_exc(),
            meson_source="server_start()"
        )

    except Exception as error:
        logging.error("server_start -", error.__str__())
        return ElementoInternalServerError(
            origin='MESON',
            error=f'Internal Server Error - {error.__str__()}',
            trace=traceback.format_exc(),
            meson_source='server_start()',
        )


@app.post("/api/v1.0/stop")
async def server_stop(req: Request):
    try:
        to_stop = await req.json()
        service_country = req.headers["service_country"] if "service_country" in req.headers.keys() else os.getenv("PROVIDER_REGION")
        vm_uuid = get_from_dict(to_stop, "vm_uuid")
        client_uuid = get_from_dict(to_stop, "client_uuid")

        try:
            stop_server(client_uuid, vm_uuid, service_country)
        except Exception as error:
            logging.error("server_stop -", error.__str__())
            return ElementoNotFound(
                origin="MESON",
                error=f"Not found - {error.__str__()}",
                trace=traceback.format_exc(),
                meson_source="server_start()"
            )

        return JSONResponse(
            status_code=202,
            content={"success": f"Stopping VM {vm_uuid}"}
        )

    except requests.HTTPError as http_err:
        logging.error("server_start -", http_err.__str__())
        return ElementoTooEarly(
            origin="MESON",
            error=f"Too early - {http_err.__str__()}",
            trace=traceback.format_exc(),
            meson_source="server_start()"
        )

    except Exception as error:
        logging.error("server_stop -", error.__str__())
        return ElementoInternalServerError(
            origin='MESON',
            error=f'Internal Server Error - {error.__str__()}',
            trace=traceback.format_exc(),
            meson_source='server_start()',
        )


@app.post("/api/v1.0/restart")
async def server_restart(req: Request):
    try:
        to_start = await req.json()
        service_country = req.headers["service_country"] if "service_country" in req.headers.keys() else os.getenv("PROVIDER_REGION")
        vm_uuid = get_from_dict(to_start, "vm_uuid")
        client_uuid = get_from_dict(to_start, "client_uuid")

        try:
            restart_server(client_uuid, vm_uuid, service_country)
        except Exception as error:
            logging.error("server_restart -", error.__str__())
            return ElementoNotFound(
                origin="MESON",
                error=f"Not found - {error.__str__()}",
                trace=traceback.format_exc(),
                meson_source="server_start()"
            )

        return JSONResponse(
            status_code=202,
            content={"success": f"Restarting VM {vm_uuid}"}
        )

    except requests.HTTPError as http_err:
        logging.error("server_start -", http_err.__str__())
        return ElementoTooEarly(
            origin="MESON",
            error=f"Too early - {http_err.__str__()}",
            trace=traceback.format_exc(),
            meson_source="server_start()"
        )

    except Exception as error:
        logging.error("server_start -", error.__str__())
        return ElementoInternalServerError(
            origin='MESON',
            error=f'Internal Server Error - {error.__str__()}',
            trace=traceback.format_exc(),
            meson_source='server_start()',
        )


@app.get("/api/v1.0/metrics")
async def server_metrics(req: Request):
    try:
        

        service_country = req.headers["service_country"] if "service_country" in req.headers.keys() else os.getenv("PROVIDER_REGION")
        try:
            client_uuid = req.query_params.get("client_uuid")
        except Exception:
            return ElementoBadRequest(
                origin="MESON",
                error="Bad Request",
                field_errors=[
                    BadRequestFieldError(
                        field="client_uuid",
                        where="BODY",
                        error="WRONG_VALUE",
                        type="str",
                        expected_value="550e8400-e29b-41d4-a716-446655440000",
                    )
                ],
                docs_url="",
                trace=traceback.format_exc(),
                meson_source="server_metrics()",
            )
        servers_dict = get_servers_metrics(client_uuid, service_country)

        return JSONResponse(
            status_code=200,
            content={"provider": os.getenv("PROVIDER"), "vms": servers_dict},
        )
    except Exception:
        return ElementoInternalServerError(
            origin="MESON",
            error="Internal Server Error",
            trace=traceback.format_exc(),
            meson_source="server_metrics()",
        )


@app.get("/api/v1.0/metrics/{vm_uuid}")
async def server_metrics_single(req: Request, vm_uuid: str):
    try:
        service_country = req.headers["service_country"] if "service_country" in req.headers.keys() else os.getenv("PROVIDER_REGION")
        try:
            client_uuid = req.query_params.get("client_uuid")
        except Exception:
            return ElementoBadRequest(
                origin="MESON",
                error="Bad Request",
                field_errors=[
                    BadRequestFieldError(
                        field="client_uuid",
                        where="BODY",
                        error="WRONG_VALUE",
                        type="str",
                        expected_value="550e8400-e29b-41d4-a716-446655440000",
                    )
                ],
                docs_url="",
                trace=traceback.format_exc(),
                meson_source="server_metrics_single()",
            )
        server_info = get_servers_metrics(client_uuid, vm_uuid, service_country)

        if server_info is None:
            return ElementoNotFound(
                origin="MESON",
                error="Error during retrieve machine metrics",
                trace=traceback.format_exc(),
                meson_source="server_metrics_single()",
            )
        return JSONResponse(
            status_code=200,
            content={"provider": os.getenv("PROVIDER"), "vms": server_info},
        )

    except Exception:
        return ElementoInternalServerError(
            origin="MESON",
            error="Internal Server Error",
            trace=traceback.format_exc(),
            meson_source="server_metrics_single()",
        )
