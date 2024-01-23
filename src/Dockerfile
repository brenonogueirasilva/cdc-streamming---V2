ARG TAG=latest
FROM gcr.io/dataflow-templates-base/python39-template-launcher-base:${TAG}

ARG WORKDIR=/opt/dataflow
RUN mkdir -p ${WORKDIR}
WORKDIR ${WORKDIR}

COPY . ${WORKDIR}/


ENV FLEX_TEMPLATE_PYTHON_REQUIREMENTS_FILE=${WORKDIR}/requirements.txt
ENV FLEX_TEMPLATE_PYTHON_PY_FILE=${WORKDIR}/dataflow-cdc-stream.py

RUN apt-get update \
    && pip install --no-cache-dir --upgrade pip \
    && pip install 'apache-beam[gcp]==2.40.0' \
    && pip install -U -r ${WORKDIR}/requirements.txt

ENV PIP_NO_DEPS=True

