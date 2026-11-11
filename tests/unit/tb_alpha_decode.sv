module tb_alpha_decode;
    timeunit 1ns;
    timeprecision 1ps;

    import alpha_decode_pkg::*;
    typedef logic [63:0] check_word_t;

    logic [31:0] instruction = 32'd0;
    decode_result_t decoded;
    decode_result_t expected;
    logic [87:0] expected_bits;
    string selected_test;
    string active_test;
    integer unsigned initial_seed = 12345;
    integer tests_run = 0;
    integer tests_failed = 0;
    integer checks = 0;
    integer failures = 0;
    integer total_checks = 0;
    integer vector_index = 0;

    alpha_decode dut (.instruction_i(instruction), .decoded_o(decoded));

    task automatic check_field(
        input string field_name,
        input check_word_t actual,
        input check_word_t wanted
    );
        checks = checks + 1;
        if (actual !== wanted) begin
            failures = failures + 1;
            if (failures <= 8)
                $display("SA_CHECK %s vector=%0d instruction=0x%08h field=%s expected=0x%016h actual=0x%016h",
                         active_test, vector_index, instruction, field_name, wanted, actual);
        end
    endtask

    task automatic check_record();
        check_field("supported",  check_word_t'(decoded.supported),  check_word_t'(expected.supported));
        check_field("op",         check_word_t'(decoded.op),         check_word_t'(expected.op));
        check_field("rs1_used",   check_word_t'(decoded.rs1_used),   check_word_t'(expected.rs1_used));
        check_field("rs2_used",   check_word_t'(decoded.rs2_used),   check_word_t'(expected.rs2_used));
        check_field("rd_written", check_word_t'(decoded.rd_written), check_word_t'(expected.rd_written));
        check_field("imm_valid",  check_word_t'(decoded.imm_valid),  check_word_t'(expected.imm_valid));
        check_field("rs1",        check_word_t'(decoded.rs1),        check_word_t'(expected.rs1));
        check_field("rs2",        check_word_t'(decoded.rs2),        check_word_t'(expected.rs2));
        check_field("rd",         check_word_t'(decoded.rd),         check_word_t'(expected.rd));
        check_field("imm",        decoded.imm,                      expected.imm);
    endtask

    task automatic run_test(input string name);
        integer file_handle;
        integer scanned;
        if (selected_test == "all" || selected_test == name) begin
            active_test = name;
            checks = 0;
            failures = 0;
            vector_index = 0;
            tests_run = tests_run + 1;
            file_handle = $fopen({"vectors/", name, ".txt"}, "r");
            if (file_handle == 0)
                $fatal(1, "Cannot open vectors for %s", name);
            while (!$feof(file_handle)) begin
                scanned = $fscanf(file_handle, "%h %h\n", instruction, expected_bits);
                if (scanned == 2) begin
                    expected = decode_result_t'(expected_bits);
                    vector_index = vector_index + 1;
                    #1;
                    check_record();
                end else if (!$feof(file_handle)) begin
                    $fatal(1, "Malformed vector in %s after vector %0d", name, vector_index);
                end
            end
            $fclose(file_handle);
            if (vector_index == 0)
                $fatal(1, "Empty vector file for %s", name);
            total_checks = total_checks + checks;
            if (failures != 0)
                tests_failed = tests_failed + 1;
            $display("SA_RESULT %s %s checks=%0d failures=%0d", name,
                     failures == 0 ? "PASS" : "FAIL", checks, failures);
        end
    endtask

`ifdef VERILATOR
    initial begin
        if ($test$plusargs("WAVES")) begin
            $dumpfile("trace.vcd");
            $dumpvars(0, tb_alpha_decode);
        end
    end
`endif

    initial begin
        if ($bits(decode_result_t) != 88)
            $fatal(1, "Decode record layout changed; update its vector contract explicitly");
        if (!$value$plusargs("TEST=%s", selected_test))
            selected_test = "all";
        if ($value$plusargs("SEED=%d", initial_seed)) begin end
        run_test("memory_formats");
        run_test("operate_registers");
        run_test("operate_literals");
        run_test("branch_offsets");
        run_test("register_roles");
        run_test("unsupported");
        run_test("no_stale_controls");
        run_test("random_formats");
        if (tests_run == 0)
            $fatal(1, "Unknown TEST=%s", selected_test);
        $display("SA_SUMMARY tests=%0d failed=%0d checks=%0d seed=%0d",
                 tests_run, tests_failed, total_checks, initial_seed);
        $finish;
    end

    initial begin
        #1000000;
        $fatal(1, "Testbench simulation-time limit exceeded");
    end
endmodule
