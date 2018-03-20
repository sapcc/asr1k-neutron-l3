class BaseEntityManager(object):
    def __init__(self, api, entity):
        self._api = api
        self._entity = entity

    def total(self):
        """Returns the total number of entities stored in Barbican."""
        params = {'limit': 0, 'offset': 0}
        resp = self._api.get(self._entity, params=params)

        return resp['total']