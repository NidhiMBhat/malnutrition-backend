#!/usr/bin/env bash
# exit on error
set -o errexit

# 1. Force install build tools and six globally first
pip install --upgrade pip setuptools wheel six

# 2. Install the requirements BUT disable "build isolation"
# This flag tells pip: "Don't ignore the 'six' I just installed above."
pip install --no-build-isolation -r requirements.txt
