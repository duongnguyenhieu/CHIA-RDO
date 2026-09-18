set parallelism [lindex $argv 0]
set output_dir [file normalize [lindex $argv 1]]
file mkdir $output_dir

set status "STARTED"
set error_message ""
set implementation_stage "none"

if {[catch {
  read_verilog -sv rtl/rdo_pe.sv build/phase7/generated/full_rdo_codec_4x4.sv rtl/full_rdo_mvp_4x4.sv rtl/full_rdo_pway.sv
  read_xdc rtl/constraints/kv260.xdc
  synth_design -top full_rdo_pway -part xck26-sfvc784-2LV-c -mode out_of_context -generic "P=$parallelism"
  set status "SYNTH_PASS"
  set implementation_stage "synthesis"
  report_utilization -file $output_dir/utilization_synth.rpt
} error_message]} {
  set status "SYNTH_FAIL"
} elseif {[catch {
  opt_design
  place_design
  set status "PLACE_PASS"
  set implementation_stage "placement"
  report_utilization -file $output_dir/utilization_place.rpt
  report_timing_summary -delay_type max -max_paths 10 -file $output_dir/timing_place.rpt
} error_message]} {
  set status "PLACE_FAIL"
} elseif {[catch {
  phys_opt_design
  route_design
  set status "ROUTE_PASS"
  set implementation_stage "routing"
  report_utilization -file $output_dir/utilization_route.rpt
  report_timing_summary -delay_type max -max_paths 10 -file $output_dir/timing_summary.rpt
  report_power -file $output_dir/power.rpt
  report_methodology -file $output_dir/methodology.rpt
  write_checkpoint -force $output_dir/full_rdo_pway_routed.dcp
} error_message]} {
  set status "ROUTE_FAIL"
}

set lut_count -1
set ff_count -1
set bram_count -1
set uram_count -1
set dsp_count -1
if {$status != "SYNTH_FAIL"} {
  set lut_count [llength [get_cells -hierarchical -filter {REF_NAME =~ LUT*}]]
  set ff_count [llength [get_cells -hierarchical -filter {REF_NAME =~ FD*}]]
  set bram_count [llength [get_cells -hierarchical -filter {REF_NAME =~ RAMB*}]]
  set uram_count [llength [get_cells -hierarchical -filter {REF_NAME =~ URAM*}]]
  set dsp_count [llength [get_cells -hierarchical -filter {REF_NAME =~ DSP*}]]
}
set wns ""
set fmax_mhz ""
if {$implementation_stage == "routing" || $implementation_stage == "placement"} {
  set timing_path [get_timing_paths -delay_type max -max_paths 1]
  if {[llength $timing_path] > 0} {
    set wns [get_property SLACK $timing_path]
    set fmax_mhz [expr {1000.0 / (5.0 - $wns)}]
  }
}

set metrics [open $output_dir/metrics.txt w]
puts $metrics "p=$parallelism"
puts $metrics "status=$status"
puts $metrics "implementation_stage=$implementation_stage"
puts $metrics "error_message=[string map {\n { } \r { }} $error_message]"
puts $metrics "lut=$lut_count"
puts $metrics "ff=$ff_count"
puts $metrics "bram=$bram_count"
puts $metrics "uram=$uram_count"
puts $metrics "dsp=$dsp_count"
puts $metrics "wns_ns=$wns"
puts $metrics "fmax_mhz=$fmax_mhz"
close $metrics
