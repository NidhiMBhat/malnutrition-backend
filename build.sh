#!/usr/bin/env bash
# exit on error
set -o errexit

# 1. Force install build tools and six globally first
pip install --upgrade pip setuptools wheel six

# 2. Install the rest of the requirements
pip install -r requirements.txt
