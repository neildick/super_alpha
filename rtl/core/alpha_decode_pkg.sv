package alpha_decode_pkg;
    timeunit 1ns;
    timeprecision 1ps;

    // Internal control identifiers, not Alpha instruction opcodes.
    typedef enum logic [3:0] {
        DEC_UNSUPPORTED = 4'd0,
        DEC_LDA         = 4'd1,
        DEC_LDAH        = 4'd2,
        DEC_LDQ         = 4'd3,
        DEC_STQ         = 4'd4,
        DEC_ADDQ        = 4'd5,
        DEC_BIS         = 4'd6,
        DEC_BR          = 4'd7,
        DEC_BNE         = 4'd8
    } decode_op_t;

    typedef struct packed {
        logic         supported;
        decode_op_t   op;
        logic         rs1_used;
        logic         rs2_used;
        logic         rd_written;
        logic         imm_valid;
        logic [4:0]   rs1;
        logic [4:0]   rs2;
        logic [4:0]   rd;
        logic [63:0]  imm;
    } decode_result_t;
endpackage
