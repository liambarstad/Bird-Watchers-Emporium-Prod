FROM neo4j:5.24.2-community

USER root
COPY initialize-db.sh /initialize-db.sh
RUN chmod +x /initialize-db.sh

ENV UPDATE_FROM_DUMP=1 \
    DUMPFILE_PATH=/data/db.dump \
    DATA_DIR=/data

ENTRYPOINT ["/initialize-db.sh"]