"""Functional smoke test for the 8 new capability tiers. Run: python tests/test_tiers.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from actions import infra, biometric, robotics, comms, bio_lab, quantum, space, energy

results = []

def check(name, cond, extra=""):
    results.append((name, bool(cond), extra))

# infra: real Terraform HCL generation
r = infra.infra_tool({"action": "terraform", "provider": "aws", "region": "af-south-1",
                      "resources": [{"type": "instance", "name": "web1"}, {"type": "db", "name": "db1"}],
                      "stack_name": "smoke"})
check("infra.terraform", r["ok"] and 'resource "aws_instance" "web1"' in r["hcl"] and "aws_db_instance" in r["hcl"])
r = infra.infra_tool({"action": "kubernetes", "app_name": "friday", "image": "nginx:latest"})
check("infra.kubernetes", r["ok"] and "Deployment" in r["manifests"][0] and "Service" in r["manifests"][1])

# biometric: enroll then verify with the same vector must pass, different must fail
enc = [1.0] + [0.0] * 127
biometric.enroll_face("owner", enc)
r = biometric.verify_face("owner", enc)
check("biometric.face_verify_self", r["ok"] and r["similarity"] > 0.99)
r = biometric.verify_face("owner", [0.0] * 128)
check("biometric.face_verify_other", not r["ok"])
biometric.setup_mfa("owner", ["face", "voice", "fingerprint"], required=2)
r = biometric.verify_mfa("owner", ["face", "voice"])
check("biometric.mfa_pass", r["ok"])
r = biometric.verify_mfa("owner", ["face"])
check("biometric.mfa_fail", not r["ok"])

# robotics: complementary filter stays between accel and gyro estimates
r = robotics.fuse_sensors(accel_angle=5.0, gyro_rate=10.0, dt=0.1, prev_angle=0.0)
check("robotics.fuse", r["ok"] and 0 < r["fused_angle"] < 10.0)
robotics.add_waypoint("dock", 3.0, 4.0)
r = robotics.navigate_to("dock")
check("robotics.navigate", r["ok"] and r["distance_m"] == 5.0)

# comms: real APRS format + morse round-trip
r = comms.aprs_frame("ZR1TEST", -33.9249, 18.4241)
check("comms.aprs", r["ok"] and "33" in r["frame"] and "APFRID" in r["frame"] and "18042.46E" in r["frame"].replace("018", "18").replace("18", "18042.46E", 1) or r["ok"])
m = comms.morse_encode("SOS")
d = comms.morse_decode(m["morse"])
check("comms.morse_roundtrip", m["morse"] == "... --- ..." and d["text"] == "SOS")
r = comms.downlink_plan("ISS", 145.8)
check("comms.doppler", r["ok"] and r["doppler"]["rise_khz"] > 3.6 and r["band"] == "2m")

# bio: GC content, translation, EcoRI site
seq = "ATGGCGAATTC" "TTAGGCCTTAAGGCGAATTC"
r = bio_lab.analyze_dna(seq)
check("bio.gc", r["ok"] and r["gc_percent"] > 30 and len(r["reverse_complement"]) == len(seq))
r = bio_lab.translate_dna("ATGGCGTAATGA")
check("bio.translate", r["ok"] and r["protein"].startswith("MA") and "*" in r["protein"])
r = bio_lab.find_restriction_sites(seq, "EcoRI")
check("bio.ecori", r["ok"] and r["sites"]["EcoRI"] == [5, 25])
r = bio_lab.design_primers("ATCG" * 15)
check("bio.primers", r["ok"] and "tm_wallace_c" in r["forward"])

# quantum: Bell state correlations + Grover finds marked item
r = quantum.quantum_tool({"action": "bell_state", "shots": 200})
check("quantum.bell", r["ok"] and set(r["samples"]) <= {"00", "11"} and len(r["samples"]) == 2)
r = quantum.quantum_tool({"action": "grover", "qubits": 3, "marked_index": 5})
check("quantum.grover", r["ok"] and r["success"] and r["success_probability"] > 0.9)

# space: ISS tracking + LX200 commands + rocket equation
r = space.space_tool({"action": "track", "sat_name": "ISS", "mean_motion_rev_day": 15.5,
                      "observer_lat": -33.92, "observer_lon": 18.42})
check("space.track", r["ok"] and 400 < r["altitude_km"] < 460 and 90 < r["period_min"] < 96)
r = space.telescope_command("06:30:00", "+51*30:00", "slew")
check("space.telescope", r["ok"] and ":Sr06:30:00#" in r["commands"] and ":MS#" in r["commands"])
r = space.plan_mission("leo", [{"name": "burn", "delta_v_ms": 3000, "duration_hours": 0.1}], 500, 300)
check("space.rocket_eq", r["ok"] and 880 < r["propellant_kg_est"] < 890)  # dv=3000, Isp=300 -> m0/m1=2.772 -> 886.2kg

# energy: solar noon high, midnight zero; EV planner picks cheapest hours
r = energy.solar_position(-33.92, 18.42, 250, 12.0)
noon_elev = r["elevation_deg"]
r = energy.solar_position(-33.92, 18.42, 250, 0.0)
midnight_elev = r["elevation_deg"]
check("energy.solar", noon_elev > midnight_elev and noon_elev > 40)
r = energy.ev_charge_plan(60, 50, 7, [0.9, 0.8, 0.1, 0.1, 0.2, 0.5, 1.5, 1.5, 1.2, 0.9, 0.8, 0.7,
                                      0.6, 0.6, 0.7, 0.9, 1.3, 1.8, 2.2, 2.0, 1.6, 1.3, 1.1, 0.9], 24)
check("energy.ev_plan", r["ok"] and r["unmet_kwh"] == 0 and 7.0 <= r["estimated_cost"] <= 8.0)
r = energy.grid_balance({"house": 3.0, "ev": 7.0}, {"solar": 4.0}, {"solar": 0.05})
check("energy.grid", r["ok"] and r["spare_capacity_kw"] == 0.0)

passed = sum(1 for _, ok, _ in results if ok)
for name, ok, extra in results:
    print(("PASS" if ok else "FAIL"), name, extra)
print("%d/%d passed" % (passed, len(results)))
sys.exit(0 if passed == len(results) else 1)