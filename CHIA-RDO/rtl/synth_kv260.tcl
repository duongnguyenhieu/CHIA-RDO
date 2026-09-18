set parallelism [lindex $argv 0]
set output_dir [file normalize [lindex $argv 1]]
file mkdir $output_dir

read_verilog -sv rtl/rdo_scheduler.sv
read_xdc rtl/constraints/kv260.xdc
synth_design -top rdo_scheduler -part xck26-sfvc784-2LV-c -mode out_of_context \
  -generic "P=$parallelism PIPELINE_DEPTH=2 COST_WIDTH=48 BUFFER_DEPTH=35"
opt_design
place_design
phys_opt_design
route_design

report_utilization -file $output_dir/utilization.rpt
report_timing_summary -delay_type max -max_paths 10 -file $output_dir/timing_summary.rpt
report_methodology -file $output_dir/methodology.rpt
write_checkpoint -force $output_dir/rdo_scheduler_routed.dcp

set lut_count [llength [get_cells -hierarchical -filter {REF_NAME =~ LUT*}]]
set ff_count [llength [get_cells -hierarchical -filter {REF_NAME =~ FD*}]]
set timing_path [get_timing_paths -delay_type max -max_paths 1]
set slack [get_property SLACK $timing_path]
set fmax_mhz [expr {1000.0 / (5.0 - $slack)}]
set metrics [open $output_dir/metrics.txt w]
puts $metrics "p=$parallelism"
puts $metrics "lut=$lut_count"
puts $metrics "ff=$ff_count"
puts $metrics "wns_ns=$slack"
puts $metrics "fmax_mhz=$fmax_mhz"
close $metrics
