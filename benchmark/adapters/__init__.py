from .cognodb import CognoDBAdapter
from .neo4j import Neo4jAdapter
from .memgraph import MemgraphAdapter
from .falkordb import FalkorDBAdapter
from .arangodb import ArangoDBAdapter


ADAPTERS = {
    "cognodb": CognoDBAdapter,
    "neo4j": Neo4jAdapter,
    "memgraph": MemgraphAdapter,
    "falkordb": FalkorDBAdapter,
    "arangodb": ArangoDBAdapter,
}