// Exercise 02: implement the instruction decoder.
// Contract and tests: docs/exercises/02-instruction-decoder.md
module alpha_decode (
    input  logic [31:0] instruction_i,
    output alpha_decode_pkg::decode_result_t decoded_o
);
    timeunit 1ns;
    timeprecision 1ps;

    import alpha_decode_pkg::*;

    // TODO: your combinational decoder goes here.
    // This neutral record keeps the exercise compilable.
    assign decoded_o = '0;
endmodule
