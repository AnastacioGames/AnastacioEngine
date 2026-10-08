/* Local deterministic tests of private complement policy; no Steam login needed. */
#include "AnastacioSteam.cpp"
#include <stdexcept>
static void check(bool value, const char *message)
{ if (!value) throw std::runtime_error(message); }
int main()
{
    try {
        const uint64_t lobby = 109775241000000001ull;
        check(commandLobby(L"\"C:\\Game Dir\\Game.exe\" +connect_lobby 109775241000000001") == lobby,
              "quoted executable and real argv invite");
        check(commandLobby(L"Game.exe +connect_lobby \"109775241000000001\"") == lobby, "quoted lobby ID");
        for (const auto *command : {L"Game.exe +connect_lobby", L"Game.exe +connect_lobby -1",
                L"Game.exe +connect_lobby 109775241000000001junk", L"Game.exe +connect_lobby 480",
                L"Game.exe +connect_lobby 184467440737095516160",
                L"Game.exe other+connect_lobby 109775241000000001"})
            check(!commandLobby(command), "malformed invite rejected");
        std::array<int64, 4> sequence = {};
        check(acceptSequence(2, 10, sequence), "first snapshot");
        check(!acceptSequence(2, 9, sequence) && !acceptSequence(2, 10, sequence), "old and duplicate discarded");
        check(acceptSequence(3, 1, sequence) && acceptSequence(2, 11, sequence), "lanes independent");
        check(acceptSequence(0, 1, sequence) && acceptSequence(0, 1, sequence), "reliable lanes not filtered");
        Endpoint endpoint(nullptr);
        endpoint.event(1, 1, 0);
        for (uint32_t i = 1; i <= 1000; ++i) endpoint.event(2, i, 0);
        check(endpoint.events.size() == 1001 && endpoint.events.back().peer == 1000,
              "disconnect retained after queue threshold");
        Context context;
        context.pending = 1; context.pendingCall = 123;
        context.created.Set(123, &context, &Context::onCreated);
        context.cancelPending();
        check(!context.pending && context.pendingCall == k_uAPICallInvalid && context.abandoned.size() == 1,
              "cancel releases operation and retains cleanup handle");
        check(!context.created.IsActive(), "create callback unregistered on cancel");
        context.pending = 2; context.pendingCall = 456;
        context.cancelPending();
        check(!context.pending && context.abandoned.size() == 1, "list cancellation needs no lobby cleanup");
        context.pending = 3; context.pendingCall = 789; context.canceled = false;
        context.entered.Set(789, &context, &Context::onEntered);
        context.deadline = std::chrono::steady_clock::now() - std::chrono::seconds(1);
        context.expirePending();
        check(!context.pending && !context.entered.IsActive() && context.abandoned.size() == 2,
              "timeout cancels callback and releases next operation");
        check(context.events.size() == 1 && context.events.front().type == 6, "timeout reported to controller");
        std::puts("STEAMPOLICY PASS (argv, sequencing, disconnect queue, cancel state)");
        return 0;
    } catch (const std::exception &error) { std::fprintf(stderr, "%s\n", error.what()); return 1; }
}
