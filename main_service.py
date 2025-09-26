import json
import traceback
import logging
import uuid
import os

from __init__ import __version__
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from commons.billing import (
    add_billing_details,
    update_billing_details,
    get_pricing,
)
from commons.utils import (
    get_from_dict,
    dynamic_global_import_fun,
    try_dynamic_import_fun
)
from errors.client_errors import (
    ElementoBadRequest,
    ElementoNotFound,
    BadRequestFieldError, ElementoTooEarly
)
from errors.server_errors import (
    ElementoCreationFailed,
    ElementoInternalServerError,
    ElementoServiceUnavailable,
)

root_path = ["platforms", "software"]
prefix = "service"
methods = [
    "get_service",
    "get_all_services",
    "setup_config",
    "create",
    "delete",
]
try:
    services = {}
    for path in root_path:
        try:
            service = dynamic_global_import_fun(
                folder_path=path, prefix=prefix, methods=methods
            )
            services.update(service)
        except Exception as error:
            logging.error(f"Error importing services from {path}: {error.__str__()}")
        
        if len(services.keys()) == 0:
            raise Exception("No services found in the specified paths.")
except Exception as error:
    logging.error(error.__str__())
    exit(1)

app = FastAPI(docs_url=None)

# This is an example implementation for the routing of services supported on this specific provider.


@app.get("/")
async def health():
    PlainTextResponse(
        status_code=200,
        content=f"Hello, world! This is an Elemento Services Meson for provider {os.getenv("PROVIDER")}.",
    )


@app.get("/api/v1.0/health")
def health():
    return JSONResponse(
        status_code=200,
        content={"status": "UP", "version": __version__},
    )


@app.get("/api/v1.0/{service}/running")
async def service_description(request: Request, service: str):
    try:
        client_uuid = request.headers.get("client_uuid")

        try:
            service_country = (
                request.headers["service_country"]
                if "service_country" in request.headers.keys()
                else os.getenv("PROVIDER_REGION")
            )
        except Exception as error:
            return ElementoBadRequest(
                origin="MESON",
                error="Bad Request in 1 field",
                field_errors=[
                    BadRequestFieldError(
                        field="service_country",
                        where="HEADER",
                        error="MISSING",
                        type="str",
                        expected_value="",
                    )
                ],
                docs_url="",
                trace=traceback.format_exc(),
                meson_source="service_description()",
            )

        if services.get(service) is not None:
            response, status_code = services[service]["get_all_services"](
                client_uuid, service_country
            )
        else:
            try:
                services[service] = try_dynamic_import_fun(
                    folder_path=root_path,
                    prefix=prefix,
                    service_name=service,
                    methods=methods,
                )
                response, status_code = services[service]["get_all_services"](
                    client_uuid, service_country
                )
            except Exception as error:
                return ElementoServiceUnavailable(
                    origin="MESON",
                    error="Service unavailable",
                    trace=traceback.format_exc(),
                    meson_source="service_description()",
                    service_failed=[service],
                )

        if status_code==200:
            return JSONResponse(status_code=200, content=response)
        else:
            return ElementoInternalServerError(
                origin="PROVIDER",
                error = f"Internal Server Error: {response}",
                trace=traceback.format_exc(),
                meson_source="service_description()",
            )

    except Exception as error:
        logging.error(error.__str__())
        return ElementoInternalServerError(
            origin="MESON",
            error="Internal Server Error",
            trace=traceback.format_exc(),
            meson_source="service_description()",
        )
    

@app.get("/api/v1.0/{service}/running/{service_uid}")
async def service_description_by_id(request: Request, service: str, service_uid: str):
    try:
        client_uuid = request.headers.get("client_uuid")
    
        try:
            service_country = (
                request.headers["service_country"]
                if "service_country" in request.headers.keys()
                else os.getenv("PROVIDER_REGION")
            )
        except Exception as error:
            return ElementoBadRequest(
                origin="MESON",
                error="Bad Request in 1 field",
                field_errors=[
                    BadRequestFieldError(
                        field="service_country",
                        where="HEADER",
                        error="MISSING",
                        type="str",
                        expected_value="",
                    )
                ],
                docs_url="",
                trace=traceback.format_exc(),
                meson_source="service_description()",
            )
        
        try:
            if services.get(service) is not None:
                response, status_code = services[service]["get_service"](
                    service_uid, client_uuid, service_country
                )
            else:
                try:
                    services[service] = try_dynamic_import_fun(
                        folder_path=root_path,
                        prefix=prefix,
                        service_name=service,
                        methods=methods,
                    )
                    response, status_code = services[service]["get_service"](
                        service_uid, client_uuid, service_country
                    )
                except Exception as error:
                    return ElementoServiceUnavailable(
                        origin="MESON",
                        error="Service unavailable",
                        trace=traceback.format_exc(),
                        meson_source="service_description()",
                        service_failed=[service],
                    )
        except Exception as error:
            return ElementoNotFound(
                origin='MESON',
                error=f'Service with UID {service_uid} not found',
                trace=traceback.format_exc(),
                meson_source='get_service()'
            )

        if status_code==200 or status_code==206:
            return JSONResponse(content=response, status_code=status_code)
        else:
            return ElementoInternalServerError(
                origin="PROVIDER",
                error = f"Internal Server Error: {response}",
                trace="",
                meson_source="get_service()",
            )

    except Exception as error:
        logging.error("server_description_by_id -", error.__str__())
        return ElementoInternalServerError(
            origin="MESON",
            error="Internal Server Error",
            trace=traceback.format_exc(),
            meson_source="servers_description_by_id()",
            headers={"error": error.__str__()},
        )


@app.post("/api/v1.0/{service}/create")
async def create_service(request: Request, service: str):
    try:
        service_to_create = await request.json()
        service_country = (
            request.headers["service_country"]
            if "service_country" in request.headers.keys()
            else os.getenv("PROVIDER_REGION")
        )
        async_flag = "false"
        if request.headers.get("Async") is not None:
            async_flag = request.headers.get("Async")
        req_data = (
            get_from_dict(service_to_create, "req")
            if type(service_to_create) == dict
            else json.loads(get_from_dict(service_to_create, "req"))
        )
        client_uuid = get_from_dict(service_to_create, "client_uuid")

        ##* Verify presence of service
        if services.get(service) is None:
            try:
                services[service] = try_dynamic_import_fun(
                    folder_path=root_path,
                    prefix=prefix,
                    service_name=service,
                    methods=methods,
                )
            except Exception as error:
                return ElementoServiceUnavailable(
                    origin="MESON",
                    error="Service unavailable",
                    trace=traceback.format_exc(),
                    meson_source="create_service()",
                    service_failed=[service],
                )

        ##* START BILLING
        try:
            price = get_pricing(service_to_create)
            if price is None:
                return ElementoCreationFailed(
                    origin="MESON",
                    error="Config is not available",
                    trace=traceback.format_exc(),
                    stopped_successfully=True,
                    billing_suspended=True,
                    meson_source="service_creation()",
                )
            reseller_id = service_to_create.get("reseller_id", os.getenv("ELEMENTO_RESELLER_ID"))
            # billing_uuid = add_billing_details(
            #     target_entity=client_uuid,
            #     price_json=price,
            #     specs_json=req_data,
            #     reseller_id=reseller_id,
            # )
            billing_uuid = "3c0e660f-7735-4707-9121-575eaa459745"
        except Exception as error:
            return ElementoCreationFailed(
                origin="MESON",
                error=f"Error during {service} creation (billing phase)",
                trace=traceback.format_exc(),
                stopped_successfully=True,
                billing_suspended=True,
                meson_source="service_creation()",
            )

        ##* SETUP CONFIG
        try:
            service_config = services[service]["setup_config"](
                req_data, client_uuid, billing_uuid, service_country
            )
        except Exception as error:
            return ElementoInternalServerError(
                origin="MESON",
                error="Internal Server Error",
                trace=traceback.format_exc(),
                meson_source="create_service()",
            )

        ##* SERVICE CREATION
        try:
            service_created, status_code = services[service]["create"](
                service_config, service_country
            )
        except Exception as error:
            # update_billing_details(billing_uuid, status="ended", reseller_id=reseller_id)
            return ElementoCreationFailed(
                origin="MESON",
                error=f"Error during {service} creation",
                trace=traceback.format_exc(),
                stopped_successfully=True,
                billing_suspended=True,
                meson_source="create_service()",
            )

        if status_code==200:
            return JSONResponse(status_code=status_code, content=service_created.to_json())
        else:
            return ElementoInternalServerError(
                origin="PROVIDER",
                error = f"Internal Server Error: {service_created}",
                trace=traceback.format_exc(),
                meson_source="create_service()",
            )

    except Exception as error:
        logging.error(error.__str__())
        return ElementoInternalServerError(
            origin="MESON",
            error="Internal Server Error",
            trace=traceback.format_exc(),
            meson_source="create_service()",
        )


@app.delete("/api/v1.0/{service}/delete")
async def delete_service(request: Request, service: str):
    try:
        service_to_delete = await request.json()
        service_country = (
            request.headers["service_country"]
            if "service_country" in request.headers.keys()
            else os.getenv("PROVIDER_REGION")
        )
        client_uuid = get_from_dict(service_to_delete, "client_uuid")
        service_uid = get_from_dict(service_to_delete, "id")

        ##* Verify presence of service
        if services.get(service) is None:
            try:
                services[service] = try_dynamic_import_fun(
                    folder_path=root_path,
                    prefix=prefix,
                    service_name=service,
                    methods=methods,
                )
            except Exception as error:
                return ElementoServiceUnavailable(
                    origin="MESON",
                    error="Service unavailable",
                    trace=traceback.format_exc(),
                    meson_source="delete_service()",
                    service_failed=[service],
                )

        if service_uid is None:
            return ElementoBadRequest(
                origin="MESON",
                error="Bad Request",
                field_errors=[
                    BadRequestFieldError(
                        field="id",
                        where="BODY",
                        error="MISSING",
                        type="str",
                        expected_value="",
                    )
                ],
                docs_url="",
                trace=traceback.format_exc(),
                meson_source="delete_service()",
            )

        ##* DELETE
        try:
            billing_uuid, status_code = (
                services[service]["get_service"](
                    service_uid, client_uuid, service_country, True
                )
                if service_to_delete.get("metadata") is None
                else services[service]["get_service"](
                    service_to_delete.get("metadata"),
                    service_uid,
                    client_uuid,
                    service_country,
                )
            )
            if status_code != 200:
                raise Exception(f"Service delete failed: {billing_uuid}, status_code: {status_code}")
        except Exception as error:
            return ElementoNotFound(
                origin='MESON',
                error=f'Service with UID {service_uid} not found',
                trace=traceback.format_exc(),
                meson_source='get_service()'
            )

        try:
            response, status_code = services[service]["delete"](
                service_uid, client_uuid, service_country
            )
        except Exception as error:
            return ElementoInternalServerError(
                origin="MESON",
                error=f"Error during {service} delete",
                trace=traceback.format_exc(),
                meson_source="delete_service()",
            )

        try:
            reseller_id = service_to_delete.get("reseller_id", os.getenv("ELEMENTO_RESELLER_ID"))
            # update_billing_details(
            #     billing_uuid=billing_uuid,
            #     status="ended",
            #     reseller_id=reseller_id,
            # )
        except Exception as error:
            return ElementoInternalServerError(
                origin="MESON",
                error=f"Error during {service} stop billing",
                trace=traceback.format_exc(),
                meson_source="delete_service()",
            )

        if status_code == 200:
            return JSONResponse(
                status_code=200,
                content=f"{service} {get_from_dict(service_to_delete, 'id')} deleted successfully",
            )
        else:
            return ElementoInternalServerError(
                origin="PROVIDER",
                error = f"Internal Server Error: {response}",
                trace=traceback.format_exc(),
                meson_source="delete_service()",
            )

    except Exception as error:
        logging.error(error.__str__())
        return ElementoInternalServerError(
            origin="MESON",
            error="Internal Server Error",
            trace=traceback.format_exc(),
            meson_source="delete_service()",
        )
