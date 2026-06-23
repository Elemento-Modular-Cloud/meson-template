import datetime

from models.ComputeModel import CpuModel, MemoryModel, MiscModel, NetworkConfigModel, AuthModel, ComputeModel
from models.StorageModel import Storage


client_uuid = "079b72f8-edf1-4fa9-8b22-2b1e364acdc7"
volume_uuid = "4c291861-8622-4e19-a9a1-0e48f305ac00"
vm_uuid = "65742f3f-f0f6-4f46-bf7c-f2ce95a14bc8"
volumes = [
    Storage(
        volume_uuid=volume_uuid,
        creator_id=client_uuid,
        billing_uuid=volume_uuid,
        name="test-volume-mockup",
        private="False",
        readonly="False",
        shareable="False",
        bootable="False",
        size=40,
        creation_date=str(datetime.datetime.now()),
    )
]
machine = ComputeModel(
    client_uuid=client_uuid,
    vm_name="test-mockup",
    volumes=volumes,
    billing_uuid=vm_uuid,
    vm_uuid=vm_uuid,
    cpu=CpuModel(
        arch=["x86"],
        flags=[]
    ),
    mem=MemoryModel(),
    pci=[],
    misc=MiscModel(
        os_family="linux",
        os_flavour="ubuntu"
    ),
    network_config=NetworkConfigModel(
        ipv4="10.0.0.1",
        ipv6="::",
        mac=""
    ),
    private_network_config=NetworkConfigModel(
        ipv4="192.168.1.1",
        ipv6="::",
        mac=""
    ),
    auth=AuthModel(),
    creation_date=str(datetime.datetime.now()),
)


def list_compute(client_uuid: str) -> list[ComputeModel]:
    """Returns a list of ComputeModel objects that are owned by the given client_uuid.

    This method should check if a Compute Instance (Machine) that is running is owned by the given client_uuid,
    and return only the matching ones.

    Args:
        client_uuid (str): The client_uuid that needs to be checked.
    Returns:
        A list of ComputeModel objects that are owned by the given client_uuid.
    Raises:
        Exception:
            Raised when a fatal error happens. Should only be thrown when an unrecoverable error occurs as it when
            caught it will result in a 500 Internal Server Error API response with the given error message inside the
            Exception.
    """
    return [machine]


def get_compute_by_uuid(client_uuid: str, vm_uuid: str) -> ComputeModel:
    """Returns an ComputeModel object that is owned by the given client_uuid and has the given vm_uuid.

    This method should check if a Compute Instance (Machine) that is running is owned by the given client_uuid,
    and has the given vm_uuid, and return it if it matches.

    Args:
        client_uuid (str): The client_uuid that needs to be checked.
        vm_uuid (str): The vm_uuid that needs to be checked.
    Returns:
        An ComputeModel object that is owned by the given client_uuid and has the given vm_uuid.
    Raises:
        Exception:
            Raised when a fatal error happens. Should only be thrown when an unrecoverable error occurs as it when
            caught it will result in a 500 Internal Server Error API response with the given error message inside the
            Exception.
    """
    return machine


def is_compute_config_available(config: ComputeModel) -> ComputeModel:
    """Checks if a given configuration can be created or not.

    The given configuration will contain all necessary information to just check if it can be created or not. If the
    issue with allocation is only in RAM or CPU Slots, you can make adjustments to make the config compatible by modifying
    the ComputeModel directly. Use common sense so do not modify the configuration for CPU and RAM excessively.
    For example, if the requested RAM quantity is 512miB but only a 500miB or 1GiB config is available, the 500miB
    option should be used. Or if 6GiB are requested but the closest available configurations are 4 or 8GiB the 8GiB option
    should be used.
    Args:
        config (ComputeModel): The configuration that needs to be checked.
    Returns:
        A Machine that is compatible with your service.
    Raises:
        Exception:
            Raised when a fatal error happens. Should only be thrown when an unrecoverable error occurs as it when
            caught it will result in a 500 Internal Server Error API response with the given error message inside the
            Exception.
    """

    return machine


def create_compute(machine: ComputeModel) -> ComputeModel:
    """Receives an ComputeModels and creates it.

    Receives an ComputeModel. You need to implement a creation flow using the attributes available in the ComputeModel
    class, using all compatible attributes.

    Args:
        machine (ComputeModel): The machine that needs to be created.
    Returns:
        The ComputeModel instance containing every available detail.
        Some fields MUST be filled during the creation and added to the machine given as argument.
        Those fields are: network_interfaces, ids of volumes created during the vm creation (without the uid in the request).
    Raises:
        Exception:
            Raised when a fatal error happens. Should only be thrown when an unrecoverable error occurs as it when
            caught it will result in a 500 Internal Server Error API response with the given error message inside the
            Exception.
    """
    #! The created machine must have these informations saved into the provider fileds (ex: tags, labels, name): client_uuid, service_uuid, billing_uuid
    return machine


def delete_compute(client_uuid: str, vm_uuid: str) -> bool:
    """Delete a vm from the CSP by its client_uuid and vm_uuid.

    The client_uuid is requested for security reasons, to ensure that the user is the owner of the vm.
    If there are volumes attached to the vm it isn't possible to delete it.
    If there is only attached the boot volume (if required by the CSP) it is possible to delete the vm.

    Args:
        client_uuid (str): The client_uuid that needs to be checked.
        vm_uuid (str): The vm_uuid that needs to be checked.
    Returns:
        True if the vm has been deleted, False otherwise.
    Raises:
        Exception:
            Raised when a fatal error happens. Should only be thrown when an unrecoverable error occurs as it when
            caught it will result in a 500 Internal Server Error API response with the given error message inside the
            Exception.
    """
    True


def start_compute(client_uuid: str, vm_uuid: str) -> None:
    """Start a virtual machine (VM) for a client by its client_uuid and vm_uuid.

    The client_uuid is required to ensure that the user is the owner of the VM.
    The function checks the VM's status and starts it if it is offline.
    If all gos well the function starts the VM and returns None,
    otherwise, it raises an exception.

    Args:
        client_uuid (str): The client_uuid that needs to be checked.
        vm_uuid (str): The vm_uuid that needs to be checked.
    Raises:
        requests.HTTPError:
            Raised when the VM is not in an offline state or if there is an
            HTTP error during the request.
        Exception:
            Raised when there is an inconsistency with the client_uuid or any
            other error occurs during the process.
    """
    pass


def stop_compute(client_uuid: str, vm_uuid: str, force: bool = False) -> None:
    """Stop a virtual machine (VM) for a client by its client_uuid and vm_uuid.

    The client_uuid is required to ensure that the user is the owner of the VM.
    The function checks the VM's status and stops it if it is online.
    If the VM is already offline or there is an inconsistency with the
    client_uuid, it raises an exception.

    Args:
        client_uuid (str): The client_uuid that needs to be checked.
        vm_uuid (str): The vm_uuid that needs to be checked.
        force (bool, optional): Whether to force stop the VM. Defaults to False.

    Raises:
        Exception:
            Raised when there is an inconsistency with the client_uuid,
            the VM is already offline, or any other error occurs
            during the process.
    """
    pass


def restart_compute(client_uuid: str, vm_uuid: str) -> None:
    """Restart a virtual machine (VM) for a client by its client_uuid and vm_uuid.

    The client_uuid is required to ensure that the user is the owner of the VM.
    The function checks the VM's status and restarts it if it is offline.
    If the VM is not offline or there is an inconsistency with the
    client_uuid, it raises an exception.

    Args:
        client_uuid (str): The client_uuid that needs to be checked.
        vm_uuid (str): The vm_uuid that needs to be checked.
    Raises:
        Exception:
            Raised when there is an inconsistency with the client_uuid,
            the VM is not offline, or any other error occurs
            during the process.
    """
    pass


def get_compute_metrics(client_uuid: str, vm_uuid: str = None) -> list[str]:
    """Retrieve server metrics for a client by its client_uuid and optionally vm_uuid.

    The client_uuid is required to ensure that the user is the owner of the servers.
    The function retrieves the list of servers associated with the client and
    optionally filters by vm_uuid.
    If vm_uuid is provided, it returns the metrics for the specific server;
    otherwise, it returns metrics for all servers associated with the client.

    Args:
        client_uuid (str): The client_uuid that needs to be checked.
        vm_uuid (str, optional): The vm_uuid that needs to be checked. Defaults to None.
    Returns:
        list: A list of dictionaries containing server metrics such as itemID,
        status, creationDate, and lastUpdateDate.

    Raises:
        Exception: Raised when there is an error in retrieving information about the server.
    """
    return [
        {
            "itemID": vm_uuid,
            "status": "Active",
        }
    ]


def get_credentials(client_uuid: str, vm_uuid: str) -> dict:
    """Retrieve credentials for a virtual machine (VM) for a client by its client_uuid and vm_uuid.

    The client_uuid is required to ensure that the user is the owner of the VM.
    The function retrieves the credentials associated with the specified VM.

    Args:
        client_uuid (str): The client_uuid that needs to be checked.
        vm_uuid (str): The vm_uuid that needs to be checked.
    Returns:
        dict: A dictionary containing the credentials for the specified VM.

    Raises:
        Exception: Raised when there is an error in retrieving credentials for the VM.
    """
    return {
        "username": "admin",
        "password": "password123"
    }