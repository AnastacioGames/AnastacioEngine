# Dedicated echo server: ENet (UDP) + WebSocket (TCP), see README.md.
# Build from the repository root:
#   docker build -f source/source/gameengine/Network/tools/net_server/Dockerfile -t anastacio-net-server .

FROM ubuntu:24.04 AS build
RUN apt-get update \
	&& apt-get install -y --no-install-recommends cmake g++ make \
	&& rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY source/source/gameengine/Network source/source/gameengine/Network
COPY source/extern/enet source/extern/enet
COPY source/extern/gtest source/extern/gtest
RUN cmake -S source/source/gameengine/Network -B build -DNET_STANDALONE=ON -DCMAKE_BUILD_TYPE=Release \
	&& cmake --build build -j --target net_echo

FROM ubuntu:24.04
RUN useradd --system --no-create-home net
COPY --from=build /src/build/net_echo /usr/local/bin/net_echo
ENV UDP_PORT=7777 WS_PORT=7778
EXPOSE 7777/udp 7778/tcp
USER net
CMD ["sh", "-c", "exec net_echo server \"$UDP_PORT\" \"$WS_PORT\""]
