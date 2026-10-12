#include "pmars_proto.h"
#include <stdio.h>

int main(void) {
    pmars_proto_session_t session;
    char line[PMARS_PROTO_MAX_LINE + 1U];
    char output[PMARS_PROTO_OUTPUT_BYTES];
    size_t length = 0U;
    int ch, oversized = 0;
    pmars_proto_init(&session);
    while ((ch = getchar()) != EOF) {
        if (ch == '\n') {
            if (length < PMARS_PROTO_MAX_LINE) line[length++] = (char)ch;
            else { oversized = 1; line[PMARS_PROTO_MAX_LINE] = '\n'; }
            size_t passed = oversized ? PMARS_PROTO_MAX_LINE + 1U : length;
            if (pmars_proto_handle(&session, line, passed, output, sizeof(output))) {
                fputs(output, stdout);
                fflush(stdout);
            }
            length = 0U;
            oversized = 0;
        } else if (length < PMARS_PROTO_MAX_LINE) line[length++] = (char)ch;
        else oversized = 1;
    }
    if (length != 0U || oversized) {
        (void)pmars_proto_handle(&session, line,
                                 oversized ? PMARS_PROTO_MAX_LINE + 1U : length,
                                 output, sizeof(output));
        fputs(output, stdout);
    }
    return ferror(stdin) || ferror(stdout) ? 1 : 0;
}
