FROM ghcr.io/ggml-org/llama.cpp:server-vulkan

USER root

# Avoid interactive prompts during package install
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends mesa-vulkan-drivers vulkan-tools libvulkan1 \
    && rm -rf /var/lib/apt/lists/*

# Copy your vendor-provided Vulkan/ICD/driver artifacts into the image.
# Put them in docker/llama-server/drivers/ before building.
#COPY drivers/ /usr/local/lib/vulkan/

# Ensure the driver path is discoverable at runtime.
#ENV LD_LIBRARY_PATH=/usr/local/lib/vulkan:${LD_LIBRARY_PATH}

# Default entrypoint remains the upstream llama-server
# (Helm chart supplies args/ports/etc.).

