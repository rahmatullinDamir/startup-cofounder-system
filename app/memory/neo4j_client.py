from neo4j import GraphDatabase


class Neo4jClient:

    def __init__(self):
        self.driver = GraphDatabase.driver(
            "bolt://neo4j:7687",
            auth=("neo4j", "password")
        )

    def create_node(self, label, props):
        with self.driver.session() as session:
            result = session.run(
                f"CREATE (n:{label} $props) RETURN id(n)",
                props=props
            )

            return result.single()[0]

    def create_rel(self, a, b, rel):
        with self.driver.session() as session:
            session.run(
                """
                MATCH (x),(y)
                WHERE id(x)=$a AND id(y)=$b
                CREATE (x)-[:REL]->(y)
                """,
                a=a, b=b
            )

    def get_related_ideas(self, query):
        return self.db.query("""
            MATCH (i:Idea)-[r]->(e)
            WHERE i.content CONTAINS $query
            RETURN i, e
        """, {"query": query})
from neo4j import GraphDatabase


class Neo4jClient:

    def __init__(self):

        self.driver = GraphDatabase.driver(
            "bolt://neo4j:7687",
            auth=("neo4j", "password")
        )

    def query(self, query, params=None):

        with self.driver.session() as session:
            result = session.run(query, params or {})
            return [r.data() for r in result]