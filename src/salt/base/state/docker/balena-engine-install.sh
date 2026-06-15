#!/bin/sh

tag=$(echo "$tag" | sed 's|+|.|g')

machine=$(uname -m)

case "$machine" in
	"armv5"*)
		arch="armv5e"
		;;
	"armv6"*)
		arch="armv6l"
		;;
	"armv7l"*)
		# special case: Buster (Debian 10) only supports armv6l binaries
		os_codename=$(. /etc/os-release 2>/dev/null && echo "${VERSION_CODENAME:-}" || echo "")
		if [ "$os_codename" = "buster" ]; then
			arch="armv6l"
		else
			arch="armv7hf"
		fi
		;;
	"armv7"*)
		arch="armv7hf"
		;;
	"armv8"*)
		arch="arm64"
		;;
	"aarch64"*)
		arch="arm64"
		;;
	"x86_64")
		arch="amd64"
		;;
	*)
		echo "Unknown machine type: $machine"
		exit 1
esac

echo "balena-engine version ${tag} for arch ${arch}"

url="https://github.com/balena-os/balena-engine/releases/download/${tag}/balena-engine-${tag}-${arch}.tar.gz"

echo "Downloading and unpacking balena-engine tar into /usr/local/bin"

if ! curl -sL "$url" | sudo tar --overwrite -xzv -C /usr/local/bin --strip-components=1; then
	echo "Error: Failed to download or extract the file."
	exit 1
fi

echo "Creating balena-engine version file in /usr/local/bin"
echo "$tag" | sudo tee /usr/local/bin/balena-engine-version.txt

cat <<EOF


   Installation successful!
 _           _
| |__   __ _| | ___ _ __   __ _
| '_ \\ / _\` | |/ _ \\ '_ \\ / _\` |
| |_) | (_| | |  __/ | | | (_| |
|_.__/ \\__,_|_|\\___|_| |_|\\__,_|

the container engine for the IoT
EOF
