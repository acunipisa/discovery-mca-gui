from app.controller import DiscoveryMCAController


def print_menu():
    print("\n==============================")
    print("Discovery 3 MCA - Main Menu")
    print("==============================")
    print("1) Read supply status")
    print("2) Enable + supply")
    print("3) Disable + supply")
    print("4) Enable - supply")
    print("5) Disable - supply")
    print("6) Disable all supplies")
    print("7) Configure scope trigger")
    print("8) Set bias control voltage (HV DAC)")
    print("9) Stop bias control voltage")
    print("10) Start/arm trigger once")
    print("11) Stop scope")
    print("12) Capture once and process")
    print("13) Start MCA")
    print("14) Clear MCA spectrum")
    print("15) Show MCA summary")
    print("16) Save MCA spectrum CSV")
    print("17) Plot MCA spectrum")
    print("18) Save MCA spectrum HTML")
    print("19) Plot last buffer")
    print("20) Start test pulse ramp")
    print("21) Stop test pulse ramp")
    print("0) Exit")
    print("==============================")


def print_supply_status(status: dict):
    print("\n=== Supply Status ===")
    print(f"Master enable : {status['master_enable']}")
    print(
        f"+ Supply      : enabled={status['positive']['enabled']}  "
        f"V={status['positive']['voltage']:.6f}  "
        f"I={status['positive']['current']:.6f}"
    )
    print(
        f"- Supply      : enabled={status['negative']['enabled']}  "
        f"V={status['negative']['voltage']:.6f}  "
        f"I={status['negative']['current']:.6f}"
    )


def print_scope_config_summary(summary):
    print("\nScope configured successfully.")
    print(f"Sample rate            : {summary.sample_rate_hz} Hz")
    print(f"Buffer size            : {summary.buffer_size}")
    print(f"Expected trigger index : {summary.expected_trigger_index}")
    print(f"Trigger level          : {summary.trigger_level_v} V")
    print(
        f"Trigger edge           : {'rising' if summary.trigger_rising else 'falling'}"
    )
    print(f"Input range            : {summary.input_range_v} V")
    print(f"Offset                 : {summary.offset_v} V")


def print_capture_result(result):
    print("\n=== Capture Result ===")
    print(f"Peak           : {result.peak:.6f} V")
    print(f"Baseline       : {result.baseline:.6f} V")
    print(f"Amplitude      : {result.amplitude:.6f} V")
    print(f"Peak index     : {result.peak_index}")
    print(f"Trigger index  : {result.trigger_index_estimate}")
    print(f"Baseline window: [{result.baseline_start}:{result.baseline_end}]")


def print_mca_summary(summary: dict):
    print("\n=== MCA Summary ===")
    print(f"Channels                 : {summary['n_channels']}")
    print(
        f"Voltage range            : {summary['voltage_min']:.3f} .. {summary['voltage_max']:.3f} V"
    )
    print(f"Events seen              : {summary['event_count']}")
    print(f"Accepted                 : {summary['accepted_count']}")
    print(f"Rejected                 : {summary['rejected_count']}")
    print(f"Overflow                 : {summary['overflow_count']}")
    print(f"Underflow                : {summary['underflow_count']}")
    print(f"Elapsed time [s]         : {summary['elapsed_time_s']:.3f}")
    print(f"Accepted rate [cps]      : {summary['accepted_rate_cps']:.3f}")
    print(f"Counts in spectrum       : {summary['total_counts_in_spectrum']}")


class CLIApplication:
    def __init__(self, controller: DiscoveryMCAController | None = None):
        self.controller = controller or DiscoveryMCAController()

    def _on_mca_status(self, mca, result):
        mca.print_status_line(result)

    def _configure_scope_interactive(self):
        trigger_level = input("Trigger level [V] (default 0.2): ").strip()
        trigger_edge = (
            input("Trigger edge rising/falling (default rising): ").strip().lower()
        )

        trigger_level_v = 0.2 if trigger_level == "" else float(trigger_level)
        trigger_rising = trigger_edge != "falling"

        summary = self.controller.configure_scope(
            trigger_level_v=trigger_level_v,
            trigger_rising=trigger_rising,
        )
        print_scope_config_summary(summary)

    def run(self):
        try:
            self.controller.open()

            while True:
                print_menu()
                choice = input("Select option: ").strip()

                try:
                    if choice == "1":
                        print_supply_status(self.controller.read_supply_status())

                    elif choice == "2":
                        voltage = input(
                            "Positive supply voltage [default 5.0]: "
                        ).strip()
                        voltage = 5.0 if voltage == "" else float(voltage)
                        self.controller.enable_positive_supply(voltage)
                        print(f"\nPositive supply enabled at {voltage:.3f} V")

                    elif choice == "3":
                        self.controller.disable_positive_supply()
                        print("\nPositive supply disabled.")

                    elif choice == "4":
                        voltage = input(
                            "Negative supply voltage magnitude [default 5.0]: "
                        ).strip()
                        voltage = 5.0 if voltage == "" else float(voltage)
                        self.controller.enable_negative_supply(voltage)
                        print(f"\nNegative supply enabled at -{voltage:.3f} V")

                    elif choice == "5":
                        self.controller.disable_negative_supply()
                        print("\nNegative supply disabled.")

                    elif choice == "6":
                        self.controller.disable_all_supplies()
                        print("\nAll supplies disabled.")

                    elif choice == "7":
                        self._configure_scope_interactive()

                    elif choice == "8":
                        voltage = input("Bias control voltage [0.0 .. 1.2 V]: ").strip()
                        actual = self.controller.set_hv_voltage(float(voltage))
                        print(f"\nHV control DAC set to {actual:.6f} V")

                    elif choice == "9":
                        self.controller.stop_hv(force_zero=True)
                        print("\nHV control output stopped and forced to 0 V")

                    elif choice == "10":
                        self.controller.arm_scope()
                        print("\nScope armed and waiting for trigger.")

                    elif choice == "11":
                        self.controller.stop_scope()
                        print("\nScope stopped.")

                    elif choice == "12":
                        print("\nScope armed, waiting for trigger...")
                        result = self.controller.capture_once()
                        print_capture_result(result)

                    elif choice == "13":
                        duration_str = input(
                            "Acquisition time in seconds [empty = continuous]: "
                        ).strip()
                        duration_s = None if duration_str == "" else float(duration_str)
                        if duration_s is None:
                            print("\nMCA running continuously. Press Ctrl+C to stop.\n")
                        else:
                            print(f"\nMCA running for {duration_s:.3f} s...\n")

                        try:
                            self.controller.start_mca(
                                status_period_s=1.0,
                                duration_s=duration_s,
                                status_callback=self._on_mca_status,
                            )
                        except KeyboardInterrupt:
                            print("\nMCA stopped by user.")
                        else:
                            if duration_s is not None:
                                print("\nTimed MCA acquisition completed.")

                    elif choice == "14":
                        self.controller.clear_mca()
                        print("\nMCA spectrum cleared.")

                    elif choice == "15":
                        print_mca_summary(self.controller.mca_summary())

                    elif choice == "16":
                        filepath = input("CSV path [default spectrum.csv]: ").strip()
                        filepath = "spectrum.csv" if filepath == "" else filepath
                        self.controller.save_mca_csv(filepath)
                        print(f"\nSpectrum saved to: {filepath}")

                    elif choice == "17":
                        self.controller.plot_mca()

                    elif choice == "18":
                        filepath = input("HTML path [default spectrum.html]: ").strip()
                        filepath = "spectrum.html" if filepath == "" else filepath
                        self.controller.save_mca_html(filepath)
                        print(f"\nSpectrum HTML saved to: {filepath}")

                    elif choice == "19":
                        self.controller.plot_last_buffer()

                    elif choice == "20":
                        freq = input("Ramp frequency [Hz] (default 100): ").strip()
                        amp = input("Ramp amplitude [V] (default 1.0): ").strip()
                        offs = input("Ramp offset [V] (default -1.0): ").strip()

                        freq = 100.0 if freq == "" else float(freq)
                        amp = 1.0 if amp == "" else float(amp)
                        offs = -1.0 if offs == "" else float(offs)

                        self.controller.start_test_pulse_ramp(
                            frequency_hz=freq,
                            amplitude_v=amp,
                            offset_v=offs,
                            symmetry_percent=100.0,
                            phase_deg=0.0,
                        )
                        print("\nTest pulse ramp started on Wavegen channel 1.")

                    elif choice == "21":
                        self.controller.stop_test_pulse(force_zero=False)
                        print("\nTest pulse ramp stopped.")

                    elif choice == "0":
                        print("\nExiting...")
                        break

                    else:
                        print("\nInvalid option.")

                except Exception as e:
                    print(f"\nError: {e}")

        finally:
            self.controller.close()


def main():
    CLIApplication().run()


if __name__ == "__main__":
    main()
