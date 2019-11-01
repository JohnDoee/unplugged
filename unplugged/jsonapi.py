from collections import defaultdict


class JSONAPIObject(dict):
    """
    A JSONAPI data item.
    """

    root = None

    def __init__(self, type, id, original_object=None, links=None, populated=True):
        """
        :param type: Object type
        :param id: Object id
        :param _original_object: A dictionary that contains the original object we are trying to serialize.
                                 Used by e.g. metadata to figure out what to add.
        """
        self.id = id
        self.type = type
        self.links = links
        self._relationships = defaultdict(list)
        self._local_relationships = defaultdict(list)
        self._original_object = original_object
        self._populated = populated

    def serialize(self, request):
        """
        Turns this object into a plain JSON API object ready to be JSON encoded.
        """
        obj = {"type": self.type, "id": self.id}
        if self._populated:
            obj["attributes"] = dict(self)

        relationships = {}
        for relationship_type, relationship_list in self._relationships.items():
            r = []
            for relationship in relationship_list:
                r.append({"type": relationship.type, "id": relationship.id})
            if r:
                relationships[relationship_type] = {"data": r}

        for relationship_type, relationship_list in self._local_relationships.items():
            r = []
            for relationship in relationship_list:
                r.append(relationship.serialize(request))

            if r:
                relationships[relationship_type] = {"data": r}

        if relationships:
            obj["relationships"] = relationships

        links = {}

        if self._original_object and hasattr(self._original_object, "get_absolute_url"):
            url = self._original_object.get_absolute_url()
            if url:
                url = request.build_absolute_uri(url)
                if url:
                    links["self"] = url

        if isinstance(links.get("self"), str) and links["self"].startswith("/"):
            links["self"] = request.build_absolute_uri(links["self"])

        if self._original_object and hasattr(
            self._original_object, "get_additional_urls"
        ):
            urls = self._original_object.get_additional_urls()
            for k, url in urls.items():
                url = request.build_absolute_uri(url)
                if url:
                    links[k] = url

        if self.links:
            links.update(self.links)

        if links:
            obj["links"] = links

        return obj

    def add_relationship(self, type, obj, local=False):
        if local:
            self._local_relationships[type].append(obj)
        else:
            self._relationships[type].append(obj)
            self.root.add_included(obj)


class JSONAPIRoot:
    """
    A base to serialize listings to proper JSONAPI format.
    """

    def __init__(self):
        self.data = []
        self.included = {}  # ('type', 'id') keys mapped to a JSONAPIObject
        self.links = {}
        self.meta = {}
        self.errors = {}

    def append(self, obj):
        """
        Appends a new object to the output
        """
        obj.root = self
        self.data.append(obj)

    def add_included(self, obj):
        """
        Appends a new object that should be included (and referenced by objects in data)
        """
        obj.root = self
        self.included[(obj.type, obj.id)] = obj

    def _serialize_success(self, request):
        data = []
        for obj in self.data:
            data.append(obj.serialize(request))

        included = []
        for obj in self.included.values():
            included.append(obj.serialize(request))

        if len(data) == 1:
            data = data[0]

        obj = {"data": data, "included": included}

        if self.meta:
            obj["meta"] = self.meta

        if self.links:
            obj["links"] = self.links

        return obj

    def _serialize_errors(self, request):
        errors = self.errors.copy()

        if self.meta:
            errors["meta"] = self.meta

        if self.links:
            errors["links"] = self.links

        obj = {"errors": [errors]}

        return obj

    def serialize(self, request):
        """
        Turns the root into a JSONAPI object ready to be JSON encoded.
        """
        if self.errors:
            return self._serialize_errors(request)
        else:
            return self._serialize_success(request)

    @classmethod
    def success_status(cls, message_or_meta):
        obj = cls()
        if isinstance(message_or_meta, dict):
            obj.meta.update(message_or_meta)
        else:
            obj.meta["message"] = message_or_meta
        return obj

    @classmethod
    def error_status(
        cls,
        id_=None,
        status=None,
        code=None,
        title=None,
        detail=None,
        source_param=None,
    ):
        obj = cls()

        if id_:
            obj.errors["id"] = id_

        if status:
            obj.errors["status"] = status

        if code:
            obj.errors["code"] = code

        if title:
            obj.errors["title"] = title

        if detail:
            obj.errors["detail"] = detail

        if source_param:
            obj.errors["source"] = {"parameter": source_param}

        return obj
