# Lab 2 -- Measurement + Datapath Tuning
# Do not modify this file.
#
# Every tool (Mininet / OVS / iperf3 / ethtool / tc / matplotlib) and the OVS
# entrypoint live in the base image, built by NYCU-SDNFV/lab-images and pushed
# to GHCR. The immutable digest keeps local work and grading on the same image.
FROM ghcr.io/nycu-sdnfv/lab-base@sha256:c9b6ee4a5271038225a7ca41f541fd005e3766abf4bd70f9f924a61e24984a19
WORKDIR /workspace
