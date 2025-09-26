from models.StorageModel import ElementoStorage
from infrastructure.compute.compute_manager import volumes


def information_about_storages_by_id(volume_uuid: str, service_country: str) -> ElementoStorage:
    """Fetches information about a storage by its ID.

    Args:
        volume_uuid (str): The ID of the storage.
        service_country (str): optional, region to use.

    Returns:
        An ElementoStorage objects that match the given ID.
    """
    return volumes[0]


def information_about_storages_by_client_id(client_uuid: str, service_country: str) -> list[ElementoStorage]:
    """Fetches information about storages linked to a client ID.

    Args:
        client_uuid (str): The client ID.
        service_country (str): optional, region to use.

    Returns:
        A list of ElementoStorage objects that are linked to the given client ID.
    """
    return volumes


def is_storage_available(config: ElementoStorage, service_country: str) -> ElementoStorage:
    """Checks if a given storage is available.

    Args:
        config (ElementoStorage): The storage configuration to check.
        service_country (str): optional, region to use.

    Returns:
        The storage pricing if it is available, None otherwise, and

    """
    return volumes[0]


def create_storage(storage_data: ElementoStorage, service_country: str) -> ElementoStorage:
    """Creates a storage.

    Args:
        storage_data (ElementoStorage): The data needed to create the storage.
        service_country (str): optional, region to use.

    Returns:
        The storage ID.
    """
    return volumes[0]


def destroy_storage(volume_uuid: str, service_country: str) -> str:
    """Destroys a storage.

    Args:
        volume_uuid (str): The ID of the storage to destroy.
        service_country (str): optional, region to use.

    Returns:
        The ID of the storage that was deleted.
    """
    return volumes[0].volume_uuid
