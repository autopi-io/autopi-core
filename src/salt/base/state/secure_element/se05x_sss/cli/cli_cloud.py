#
# Copyright 2019,2020 NXP
# SPDX-License-Identifier: Apache-2.0
#
#

"""License text"""

from .cli import cloud, pass_context


@cloud.group()
@pass_context
def ibm(cli_ctx):
    """ (Not Implemented) IBM Watson Specific utilities

    This helps to handle ibm specific settings."""
    cli_ctx.vlog("IBM Watson Specific utilities")


@cloud.group()
@pass_context
def gcp(cli_ctx):
    """ (Not Implemented) GCP (Google Cloud Platform) Specific utilities

    This helps to handle GCP specific settings."""
    cli_ctx.vlog("GCP (Google Cloud Platform) Specific utilities")


@cloud.group()
@pass_context
def aws(cli_ctx):
    """ (Not Implemented) AWS (Amazon Web Services) Specific utilities

    This helps to handle AWS specific settings."""
    cli_ctx.vlog("AWS (Amazon Web Services) Specific utilities")
