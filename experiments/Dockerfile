ARG POLICY_SUMMARIZER_IMAGE=policysummarizer
FROM ${POLICY_SUMMARIZER_IMAGE}

WORKDIR /workspace

COPY requirements.txt /tmp/policysummarizer-experiment-requirements.txt
RUN pip install --no-cache-dir -r /tmp/policysummarizer-experiment-requirements.txt

COPY Dataset/ ./Dataset/
COPY experiments/ ./experiments/
COPY policysummarizer/ ./policysummarizer/

CMD ["bash"]
