/* In-process loopback transport. Extension of section 9.2: a hub lets one
 * listening endpoint accept many client endpoints (host + local tests). */

#pragma once

#include "NET_ITransport.h"

namespace net {

struct LoopbackHubState;

class LoopbackHub {
public:
	LoopbackHub();
	/* New endpoint on this hub. listen(port) registers it under that port;
	 * connect(any host, port) reaches the endpoint listening on that port. */
	std::unique_ptr<ITransport> createEndpoint();

private:
	std::shared_ptr<LoopbackHubState> m_state;
};

}  // namespace net
