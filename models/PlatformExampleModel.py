class ExampleCapabilities:
    def __init__(self):
        pass

    def to_json(self):
        try:
            return {
                "key": "value"
            }
        except Exception as ex:
            raise Exception(f"Cannot create JSON (ExampleCapabilities): {ex}")


class ExampleModel:
    def __init__(self, metadata: dict, resources: dict, client_uuid: str, billing_uuid: str, capabilities: ExampleCapabilities = None):
        pass

    def to_json(self):
        try:
            return {
                "metadata": "value",
                "capabilities":  "value",
                "resources":  "value",
                "client_uuid":  "value",
                "billing_uuid":  "value"
            }
        except Exception as ex:
            raise Exception(f"Cannot create JSON (ExampleModel): {ex}")
