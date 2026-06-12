from models.StorageModel import Storage
from infrastructure.compute.compute_manager import volumes


def get_storage_by_uuid(volume_uuid: str) -> Storage:
    """Fetches information about a storage by its ID.

    Args:
        volume_uuid (str): The ID of the storage.
    Returns:
        An Storage objects that match the given ID.
    """
    return volumes[0]


def list_storage(client_uuid: str) -> list[Storage]:
    """Fetches information about storages linked to a client ID.

    Args:
        client_uuid (str): The client ID.
    Returns:
        A list of Storage objects that are linked to the given client ID.
    """
    return volumes


def is_storage_config_available(config: Storage) -> Storage:
    """Checks if a given storage is available.

    Args:
        config (Storage): The storage configuration to check.
    Returns:
        The storage pricing if it is available, None otherwise, and

    """
    return volumes[0]


def create_storage(storage_data: Storage) -> Storage:
    """Creates a storage.

    Args:
        storage_data (Storage): The data needed to create the storage.
    Returns:
        The storage ID.
    """
    return volumes[0]


def delete_storage(volume_uuid: str) -> str:
    """Destroys a storage.

    Args:
        volume_uuid (str): The ID of the storage to destroy.
    Returns:
        The ID of the storage that was deleted.
    """
    return volumes[0].volume_uuid
