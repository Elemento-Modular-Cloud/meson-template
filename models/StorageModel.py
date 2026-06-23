import datetime
import os
import uuid


class Storage:

    def __init__(
        self,
        volume_uuid: str = None,
        creator_id: str = None,
        billing_uuid: str = None,
        name: str = None,
        private: bool = False,
        readonly: bool = False,
        shareable: bool = False,
        bootable: bool = False,
        clonable: bool = False,
        size: int = 0,
        priority: int = None,
        tags: list[str] = None,
        creation_date: str = None,
        notes: dict = None,
        region: str = os.environ.get("PROVIDER_REGION", "us-east1"),
        type: str = None,
        **kwargs
    ):
        self.volume_uuid = volume_uuid if volume_uuid else str(uuid.uuid4())
        self.creator_id = creator_id
        self.billing_uuid = billing_uuid
        self.name = name
        self.private = private
        self.readonly = readonly
        self.shareable = shareable
        self.bootable = bootable
        self.clonable = clonable
        self.size = int(size)
        self.priority = priority
        self.tags = tags if tags is not None else []
        self.region = region
        self.notes = notes if notes is not None else {}
        self.type = type

        if creation_date:
            self.creation_date = creation_date
        else:
            now = datetime.datetime.now()
            self.creation_date = now.strftime("%m/%d/%Y, %H:%M:%S")

        self.csp_region = region
        self.bus = kwargs.get("bus", "virtio")
        self.format_type = kwargs.get("format_type", "raw")
        self.serverurl = kwargs.get("serverurl", None)
        self.servers = kwargs.get("servers", [])

    @staticmethod
    def from_json(json_data: dict):
        return Storage(
            volume_uuid=json_data["volumeID"] if "volumeID" in json_data.keys() else None,
            creator_id=json_data["creatorID"] if "creatorID" in json_data.keys() else None,
            name=json_data["name"],
            private=json_data["private"],
            readonly=json_data["readonly"],
            shareable=json_data["shareable"],
            bootable=json_data["bootable"],
            clonable=json_data["clonable"] if "clonable" in json_data.keys() else False,
            size=json_data["size"],
            priority=json_data["priority"] if "priority" in json_data.keys() else None,
            tags=json_data["volume_tags"] if "volume_tags" in json_data.keys() else [],
            region=json_data["region"] if "region" in json_data.keys() else os.environ.get("PROVIDER_REGION"),
            type=json_data['type']  if "type" in json_data.keys() else None
        )

    @staticmethod
    def from_model(model):
        return Storage(
            volume_uuid=model.tags["volume_uuid"],
            creator_id=model.tags["creator_id"],
            billing_uuid=model.tags["billing_uuid"],
            name=model.name,
            size=model.properties["diskSizeGB"],
            private=False if model.tags["private"] == "False" else True,
            creation_date=datetime.datetime.strptime(model.properties["timeCreated"].split(".")[0],
                                                     "%Y-%m-%dT%H:%M:%S").strftime("%m/%d/%Y, %H:%M:%S")
        )

    def to_json(self):
        return {
            "region": self.region,
            "csp_region": self.region,
            "vid": self.volume_uuid,
            "volumeID": self.volume_uuid,
            "creator_id": self.creator_id,
            "billing_uuid": self.billing_uuid,
            "name": self.name,
            "private": self.private,
            "readonly": self.readonly,
            "shareable": self.shareable,
            "bootable": self.bootable,
            "clonable": self.clonable,
            "size": self.size,
            "priority": self.priority,
            "tags": self.tags,
            "creation_date": self.creation_date,
            "notes": self.notes,
        }

    def to_json_response(self) -> dict:
        env_suffix = "dev." if os.environ.get("ENV") == "development" else ""
        
        return {
            "creatorID": self.creator_id,
            "billingUUID": self.billing_uuid,
            "name": self.name,
            "private": self.private,
            "bootable": self.bootable,
            "readonly": self.readonly,
            "shareable": self.shareable,
            "clonable": self.clonable,
            "size": self.size * 10**9,
            "priority": self.priority if self.priority is not None else 50,
            "tags": self.tags,
            "volumeID": self.volume_uuid,
            "lastUpdated": self.creation_date,
            "region": self.region,
            "csp_region": self.region,
            "size_on_disk": 0,
            "bus": self.bus,
            "format_type": self.format_type,
            "server_url": self.serverurl,
            "serverurl": f"https://{os.environ.get('PROVIDER', 'provider')}.{env_suffix}meson.elemento.cloud:7772",
            "read_mb_bw": 0,
            "write_mb_bw": 0,
            "read_iops": 0,
            "write_iops": 0,
            "hw_device": None,
            "fs": None,
            "kind": None,
            "server": "0.0.0.0",
            "own": True,
            "nservers": len(self.servers),
            "servers": self.servers,
        }