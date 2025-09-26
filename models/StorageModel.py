import os

class ElementoStorage:
    """
    Describes the storage configuration of the machine.

    Use this class to create and manage a volume on the csp.
    Some ids (creator_id, volume_uuid, billing_uuid) MUST be setted inside the volume on the csp to retrieve them.
    These ids are fundamental for the Meson to work properly.

    Attributes:
        csp_region (str): The region where the volume will be created. --> maybe will be removed
        volume_uuid (str): The volume's unique identifier from Elemento (uuid4).
        creator_id (str): The creator's unique identifier from Elemento.
        billing_uuid (str): The billing's unique identifier from Elemento.
        name (str): The name of the volume that will be displayed in the response.
        private (bool): If the volume is visible only by the creator or not.
        readonly (bool): If the volume is readonly or not.
        shareable (bool): If the volume is shareable between more than one vm or not.
        bootable (bool): If the volume is bootable or not.
        size (int): The size of the volume in GB.
        creation_date (str): The date when the volume was created. It MUST be set when the volume is created(%m/%d/%Y, %H:%M:%S)
        notes (dict): A dictionary with a totally free space to add info about the volume.
        It can be used to store any kind of information useful for the Meson implementation.
        All the information won't be displayed in the Elemento's response.
    """

    def __init__(
        self,
        csp_region: str = os.getenv("PROVIDER_REGION"),
        volume_uuid: str = None,
        creator_id: str = None,
        billing_uuid: str = None,
        name: str = None,
        private: bool = False,
        readonly: bool = False,
        shareable: bool = False,
        bootable: bool = False,
        size: int = 0,
        creation_date: str = None,
        notes: dict = dict(),
    ):
        self.csp_region = csp_region
        self.volume_uuid = volume_uuid
        self.creator_id = creator_id
        self.billing_uuid = billing_uuid
        self.name = name
        self.private = private
        self.readonly = readonly
        self.shareable = shareable
        self.bootable = bootable
        self.size = int(size)
        self.creation_date = creation_date
        self.notes = notes

    def to_json(self):
        """
        A to json method to format an ElementoStorage into a general dictionary with all fields
        returns:
            A dictionary with all fields of a ElementoStorage
        """
        return {
            "csp_region": self.csp_region,
            "vid": self.volume_uuid,
            "creator_id": self.creator_id,
            "billing_uuid": self.billing_uuid,
            "name": self.name,
            "private": self.private,
            "readonly": self.readonly,
            "shareable": self.shareable,
            "bootable": self.bootable,
            "size": self.size,
            "creation_date": self.creation_date,
            "notes": self.notes,
        }

    def to_json_response(self) -> dict:
        """
        A to json method to format an ElementoStorage into a dictionary
        returns:
            A dictionary formatted for the info/accessible response
        """
        return {
            "creatorID": self.creator_id,
            "name": self.name,
            "private": self.private,
            "bootable": self.bootable,
            "readonly": self.readonly,
            "shareable": self.shareable,
            "size": self.size,
            "vid": self.volume_uuid,
        }
