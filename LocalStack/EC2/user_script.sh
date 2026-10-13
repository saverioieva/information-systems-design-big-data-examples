#!/bin/bash -xeu

apt update
apt install python3 -y
python3 -m http.server 8000
