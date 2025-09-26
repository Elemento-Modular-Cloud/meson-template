import math
import importlib
import logging
import uuid
from pathlib import Path
from typing import List
from models.ComputeModel import ElementoMachine
from models.StorageModel import ElementoStorage


logger = logging.getLogger("__name__")
TOLERANCE = 10  # TODO: define a proper tolerance


def check_storage_tolerance(
    requested: ElementoStorage, proposed: ElementoStorage
) -> bool:
    try:
        err_margin = math.sqrt(((proposed.size - requested.size) / requested.size) ** 2)
        is_config_ok = (
            err_margin <= TOLERANCE
            and proposed.private == requested.private
            and proposed.readonly == requested.readonly
            and proposed.shareable == requested.shareable
            and proposed.bootable == requested.bootable
        )
        return is_config_ok
    except Exception as error:
        raise Exception(f"check storage tolerance - {error.__str__()}")


def check_storage_params(config: ElementoStorage) -> bool:
    if (  # TODO: improve the check (considering that some fields are Models)
        config.volume_uuid is None
        or config.creator_id is None
        or config.billing_uuid is None
        or config.size is None
        or config.name is None
    ):
        return False

    return True


def check_vm_tolerance(requested: ElementoMachine, proposed: ElementoMachine) -> bool:
    try:
        err_margin_capacity = (
            (proposed.mem.capacity - requested.mem.capacity) / requested.mem.capacity
        ) ** 2
        err_margin_slots = (
            (proposed.cpu.slots - requested.cpu.slots) / requested.cpu.slots
        ) ** 2
        err_margin_overprovision = (
            (proposed.cpu.maxOverprovision - requested.cpu.maxOverprovision)
            / requested.cpu.maxOverprovision
        ) ** 2
        err_margin_freq = (
            (proposed.cpu.min_frequency - requested.cpu.min_frequency)
            / requested.cpu.min_frequency
        ) ** 2

        err_margin_global = math.sqrt(
            err_margin_capacity
            + err_margin_slots
            + err_margin_overprovision
            + err_margin_freq
        )

        is_config_ok = (
            err_margin_global <= TOLERANCE
            and proposed.misc.to_json() == requested.misc.to_json()
            and proposed.cpu.arch.sort() == requested.cpu.arch.sort()
            and (
                [pci.to_json() for pci in proposed.pci].sort()
                if proposed.pci is not None
                else []
            )
            == (
                [pci.to_json() for pci in requested.pci].sort()
                if requested.pci is not None
                else []
            )
        )
        return is_config_ok
    except Exception as error:
        raise Exception(f"check vm tolerance - {error.__str__()}")


def check_vm_params(config: ElementoMachine) -> bool:
    if (  # TODO: improve the check (considering that some fields are Models)
        config.client_uuid is None
        or config.billing_uuid is None
        or config.vm_uuid is None
        or config.cpu is None
        or config.mem is None
        or config.misc is None
    ):
        return False

    return True


def get_from_dict(d: dict, key: str, key2: str = None):
    try:
        return d[key] if key2 is None else d[key][key2]
    except:
        err_msg = (
            f"dictionary key '{key}' is not present in {d}"
            if key2 is None
            else f"dictionary key '{key}'|'{key2}' is not present in {d}"
        )
        raise KeyError(err_msg)


def dynamic_global_import_path(
    folder_path: str, prefix: str, methods: List[str]
) -> dict:
    try:
        folder = Path(folder_path)
        utils_files = [
            file.name
            for file in folder.iterdir()
            if file.is_file()
            and prefix in file.name
            and prefix != (file.name).replace(".py", "")
        ]

        services = {}
        for util_class in utils_files:
            file_name = util_class.replace(".py", "").split("_")
            service_name = file_name[1]
            function_name = "_".join(file_name[2:])

            services[service_name] = {}
            for method in methods:
                if method == function_name:
                    services[service_name][method] = folder_path + method

        return services

    except Exception as error:
        raise Exception(error)


def try_dynamic_import_path(
    folder_path: str, service_name: str, prefix: str, methods: List[str]
):
    service = {}
    try:
        folder = Path(folder_path)
        services_provided = {
            file.name.replace(".py", "").split("_")[1]
            for file in folder.iterdir()
            if file.is_file()
            and prefix in file.name
            and prefix != (file.name).replace(".py", "")
        }

        if service_name not in services_provided:
            raise Exception(f"Service {service_name} does not exist")

        for method in methods:
            file_path = folder / method
            if file_path.exists():
                service[method] = folder_path + method

        return service
    except Exception as error:
        raise Exception(error)


def dynamic_global_import_fun(
    folder_path: str, prefix: str, methods: List[str]
) -> dict:
    try:
        services = {}
        folder = Path(folder_path)
        utils_files = [
            file.name
            for file in folder.iterdir()
            if file.is_file()
            and prefix in file.name
            and prefix != (file.name).replace(".py", "")
        ]

        for util_class in utils_files:
            module_name = (
                folder_path.replace("/", ".") + "." + util_class.replace(".py", "")
            )
            module = importlib.import_module(module_name)

            service_name = util_class.replace(f"{prefix}_", "").replace(".py", "")
            services[service_name] = {}
            for method in methods:
                imported_fun = getattr(module, method)
                services[service_name][method] = imported_fun

        return services

    except Exception as error:
        raise Exception(error)


def try_dynamic_import_fun(
    folder_path: str, service_name: str, prefix: str, methods: List[str]
):
    service = {}
    try:
        file_name = f"{prefix}_" + service_name
        module_name = folder_path.replace("/", ".") + "." + file_name
        module = importlib.import_module(module_name)
        for method in methods:
            imported_fun = getattr(module, method)
            service[method] = imported_fun

        return service
    except Exception as error:
        raise Exception(error)


def dynamic_global_import_class(
    folder_path: str, prefix: str, class_suffix: str
) -> dict:
    try:
        folder = Path(folder_path)
        utils_files = [
            file.name
            for file in folder.iterdir()
            if file.is_file()
            and prefix in file.name
            and prefix != (file.name).replace(".py", "")
        ]

        services = {}
        for util_class in utils_files:
            module_name = folder_path + "." + util_class.replace(".py", "")
            module = importlib.import_module(module_name)

            service_name = util_class.replace(f"{prefix}_", "").replace(".py", "")
            imported_class = getattr(
                module, service_name.capitalize() + class_suffix.capitalize()
            )

            services[service_name] = imported_class()

        return services

    except Exception as error:
        raise Exception(error)


def try_dynamic_import_class(
    folder_path: str, filename: str, prefix: str, class_suffix: str
):
    try:
        module_name = folder_path + "." + filename.replace(".py", "")
        module = importlib.import_module(module_name)
        class_name = filename.replace(f"{prefix}_", "").replace(".py", "")
        imported_class = getattr(
            module, class_name.capitalize() + class_suffix.capitalize()
        )
        return imported_class()
    except Exception as error:
        raise Exception(error)


def int_to_uuid(id: int):
    try:
        return str(uuid.UUID(int=int(id)))
    except Exception as e:
        raise Exception(e)


def uuid_to_int(id: uuid):
    try:
        return uuid.UUID(id).int
    except Exception as e:
        raise Exception(e)