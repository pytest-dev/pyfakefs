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

"""Typer commands used to exercise Path annotation conversion."""

from __future__ import annotations

import pathlib
from pathlib import Path
from typing import Annotated

import typer

direct_app = typer.Typer(rich_markup_mode=None)
module_app = typer.Typer(rich_markup_mode=None)


@direct_app.command()
def copy_direct(
    source: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    target: Path,
):
    target.write_text(source.read_text(encoding="utf8"), encoding="utf8")
    typer.echo(target.read_text(encoding="utf8"))


@module_app.command()
def copy_module(
    source: Annotated[pathlib.Path, typer.Argument(exists=True, dir_okay=False)],
    target: pathlib.Path,
):
    target.write_text(source.read_text(encoding="utf8"), encoding="utf8")
    typer.echo(target.read_text(encoding="utf8"))
