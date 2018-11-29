# Copyright 2018 John McGehee. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Prerequisites:
# * Install Docker
# * Clone pyfakefs

FROM ubuntu:16.04
MAINTAINER jmcgeheeiv@users.noreply.github.com

# The Ubuntu base container does not specify a locale.
# pyfakefs tests require at least Latin1 character set.
RUN apt-get update && apt-get install -y locales
RUN locale-gen en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

RUN apt-get update && apt-get install -y python3-pip # python3
RUN apt-get clean
COPY . /usr/local/pyfakefs
WORKDIR /usr/local/pyfakefs
RUN pip3 install -r requirements.txt
RUN pip3 install -r extra_requirements.txt

RUN useradd -u 1000 pyfakefs
USER pyfakefs

ENV PYTHONPATH /usr/local/pyfakefs
CMD ["python3", "-m", "pyfakefs.tests.all_tests"]
#CMD ["python3", "-m", "pytest", "pyfakefs/tests/pytest_plugin_test.py"]

