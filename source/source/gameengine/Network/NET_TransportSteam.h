/* SPDX-License-Identifier: GPL-2.0-or-later */
#pragma once
#include "NET_ITransport.h"
namespace net {
class AnastacioPlugin;
std::unique_ptr<ITransport> createAnastacioSteamTransport(AnastacioPlugin &service);
// Diagnostic local SDK pair, not an Internet/relay test. Endpoints start connected.
bool createAnastacioSteamSocketPair(AnastacioPlugin &service,
    std::unique_ptr<ITransport> &first, std::unique_ptr<ITransport> &second);
}
