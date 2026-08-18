from .base import GraphDatabaseAdapter


class ArangoDBAdapter(GraphDatabaseAdapter):

    name = "ArangoDB"

    def connect(self):
        raise NotImplementedError

    def close(self):
        pass

    def health_check(self):
        raise NotImplementedError

    def clear_database(self):
        raise NotImplementedError

    def create_schema(self):
        raise NotImplementedError

    def load_nodes(self, users):
        raise NotImplementedError

    def load_relationships(self, relationships):
        raise NotImplementedError

    def point_lookup(self, user_id):
        raise NotImplementedError

    def indexed_lookup(self, user_id):
        raise NotImplementedError

    def traverse(self, user_id, depth):
        raise NotImplementedError

    def aggregation(self):
        raise NotImplementedError

    def write_test_record(self, source_id, target_id):
        raise NotImplementedError

    def delete_test_record(self, source_id, target_id):
        raise NotImplementedError

    def get_resource_usage(self):
        return {
            "cpu": "not observable",
            "memory": "not observable",
            "storage": "not observable",
        }