FROM apache/nifi:latest

# temp root for installation steps
USER root

# Download ClickHouse JDBC Driver
RUN curl -L "https://github.com/ClickHouse/clickhouse-java/releases/download/v0.9.4/clickhouse-jdbc-0.9.4-all.jar" \
        -o /opt/nifi/nifi-current/lib/clickhouse-jdbc-0.9.4-all.jar && \
        chown 1000:1000 /opt/nifi/nifi-current/lib/clickhouse-jdbc-0.9.4-all.jar

# Download MySQL JDBC Driver (Connector/J)
# Using version 9.5.0 as a stable reference
RUN curl -L "https://repo1.maven.org/maven2/com/mysql/mysql-connector-j/9.5.0/mysql-connector-j-9.5.0.jar" \
        -o /opt/nifi/nifi-current/lib/mysql-connector-j-9.5.0.jar && \
        chown 1000:1000 /opt/nifi/nifi-current/lib/mysql-connector-j-9.5.0.jar

# 1. Create the directory inside the container so ECS has a place to mount
RUN mkdir -p /opt/nifi/nifi-current/flow_config && \
        chown -R 1000:1000 /opt/nifi/nifi-current/flow_config

# 2. Redirect NiFi to look for flow.json.gz in this new persistent folder
RUN sed -i -e 's|^nifi.flow.configuration.file=.*$|nifi.flow.configuration.file=/opt/nifi/nifi-current/flow_config/flow.json.gz|' \
        -e 's|^nifi.flow.configuration.archive.dir=.*$|nifi.flow.configuration.archive.dir=/opt/nifi/nifi-current/flow_config/archive|' \
        conf/nifi.properties


# Download PostgreSQL JDBC Driver
RUN curl -L "https://jdbc.postgresql.org/download/postgresql-42.7.1.jar" \
        -o /opt/nifi/nifi-current/lib/postgresql-42.7.1.jar && \
        chown 1000:1000 /opt/nifi/nifi-current/lib/postgresql-42.7.1.jar







# Download MariaDB JDBC Driver
RUN curl -L "https://repo1.maven.org/maven2/org/mariadb/jdbc/mariadb-java-client/3.3.3/mariadb-java-client-3.3.3.jar" \
        -o /opt/nifi/nifi-current/lib/mariadb-java-client-3.3.3.jar && \
        chown 1000:1000 /opt/nifi/nifi-current/lib/mariadb-java-client-3.3.3.jar


# Download Oracle JDBC Driver 23c
RUN curl -L "https://repo1.maven.org/maven2/com/oracle/database/jdbc/ojdbc11/23.3.0.23.09/ojdbc11-23.3.0.23.09.jar" \
        -o /opt/nifi/nifi-current/lib/ojdbc11-23.3.0.23.09.jar && \
        chown 1000:1000 /opt/nifi/nifi-current/lib/ojdbc11-23.3.0.23.09.jar


# Download Microsoft SQL Server JDBC Driver
RUN curl -L "https://repo1.maven.org/maven2/com/microsoft/sqlserver/mssql-jdbc/12.6.1.jre11/mssql-jdbc-12.6.1.jre11.jar" \
        -o /opt/nifi/nifi-current/lib/mssql-jdbc-12.6.1.jre11.jar && \
        chown 1000:1000 /opt/nifi/nifi-current/lib/mssql-jdbc-12.6.1.jre11.jar


# Download DataStax Cassandra Java Driver
RUN curl -L "https://repo1.maven.org/maven2/com/datastax/oss/java-driver-core/4.17.0/java-driver-core-4.17.0.jar" \
        -o /opt/nifi/nifi-current/lib/cassandra-driver-core-4.17.0.jar && \
        chown 1000:1000 /opt/nifi/nifi-current/lib/cassandra-driver-core-4.17.0.jar


# Download MongoDB Sync Driver
RUN curl -L "https://repo1.maven.org/maven2/org/mongodb/mongodb-driver-sync/5.2.1/mongodb-driver-sync-5.2.1.jar" \
        -o /opt/nifi/nifi-current/lib/mongodb-driver-sync-5.2.1.jar && \
        chown 1000:1000 /opt/nifi/nifi-current/lib/mongodb-driver-sync-5.2.1.jar


# Download Jedis - Redis Java Client
RUN curl -L "https://repo1.maven.org/maven2/redis/clients/jedis/5.1.0/jedis-5.1.0.jar" \
        -o /opt/nifi/nifi-current/lib/jedis-5.1.0.jar && \
        chown 1000:1000 /opt/nifi/nifi-current/lib/jedis-5.1.0.jar


# Download Elasticsearch REST Client
RUN curl -L "https://repo1.maven.org/maven2/org/elasticsearch/client/elasticsearch-rest-client/8.11.3/elasticsearch-rest-client-8.11.3.jar" \
        -o /opt/nifi/nifi-current/lib/elasticsearch-rest-client-8.11.3.jar && \
        chown 1000:1000 /opt/nifi/nifi-current/lib/elasticsearch-rest-client-8.11.3.jar

# ============================================================
# NEW JARS WILL BE ADDED AUTOMATICALLY ABOVE THIS LINE
# DO NOT REMOVE THIS COMMENT - IT'S USED BY THE CI PIPELINE
# ============================================================

# Revert to NiFi user for running NiFi
USER 1000

## notes for future purpose:
