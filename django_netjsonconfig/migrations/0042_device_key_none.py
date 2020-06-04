# Generated by Django 3.0.3 on 2020-02-26 16:54

import django.core.validators
from django.db import migrations
import openwisp_utils.base
import re


class Migration(migrations.Migration):

    dependencies = [
        ('django_netjsonconfig', '0041_update_context_data'),
    ]

    operations = [
        migrations.AlterField(
            model_name='device',
            name='key',
            field=openwisp_utils.base.KeyField(
                blank=True,
                db_index=True,
                default=None,
                help_text='unique device key',
                max_length=64,
                unique=True,
                validators=[
                    django.core.validators.RegexValidator(
                        re.compile('^[^\\s/\\.]+$'),
                        code='invalid',
                        message='This value must not contain spaces, dots or slashes.',
                    )
                ],
            ),
        ),
    ]
