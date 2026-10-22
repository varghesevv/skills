#!/usr/bin/env bash
# Create (or update) the Lightsail alarms for the demo instance and send them to one email.
# Run once from a machine with AWS credentials that may use Lightsail (your admin profile):
#
#   ALARM_EMAIL=you@example.com ./infra/scripts/setup-alarms.sh
#
# Lightsail emails a confirmation link to that address; the alarms only notify after you
# click it. Re-running is safe: alarms are updated in place. Terraform has no resource for
# Lightsail alarms, which is why this is a script. Nothing secret is read or printed.
set -euo pipefail

instance="${INSTANCE_NAME:-skills}"
region="${AWS_REGION:-ap-south-1}"
: "${ALARM_EMAIL:?Set ALARM_EMAIL to the address that should receive alarms}"

lightsail() { aws lightsail --region "$region" "$@"; }

# Registers the address (Lightsail sends the verification email).
lightsail create-contact-method --protocol Email --contact-endpoint "$ALARM_EMAIL" >/dev/null \
  || echo "Contact method already exists or is pending verification; continuing."

# name | metric | operator | threshold | periods (5 minutes each) | description
alarms=(
  "cpu-high|CPUUtilization|GreaterThanOrEqualToThreshold|85|3|CPU at 85% or more for 15 minutes"
  "status-check-failed|StatusCheckFailed|GreaterThanOrEqualToThreshold|1|2|The instance failed its status checks"
  "burst-capacity-low|BurstCapacityPercentage|LessThanOrEqualToThreshold|20|2|CPU burst credits nearly used up"
  "network-out-high|NetworkOut|GreaterThanOrEqualToThreshold|2000000000|3|Unusually high outbound traffic (bytes per 5 minutes)"
)

for entry in "${alarms[@]}"; do
  IFS='|' read -r name metric operator threshold periods _ <<<"$entry"
  lightsail put-alarm \
    --alarm-name "${instance}-${name}" \
    --metric-name "$metric" \
    --monitored-resource-name "$instance" \
    --comparison-operator "$operator" \
    --threshold "$threshold" \
    --evaluation-periods "$periods" \
    --datapoints-to-alarm "$periods" \
    --treat-missing-data breaching \
    --contact-protocols Email \
    --notification-triggers ALARM \
    --notification-enabled >/dev/null
  echo "Alarm ready: ${instance}-${name}"
done

echo "Now open the confirmation email sent to ${ALARM_EMAIL} and click the link."
