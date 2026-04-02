"""
SQLite database models — tracks every post, its status, and performance.
Stored locally on Railway's persistent disk.
"""

import os
from datetime import datetime
from peewee import (
    SqliteDatabase, Model, CharField, TextField,
    DateTimeField, BooleanField, IntegerField, FloatField
)

DB_PATH = os.getenv("DB_PATH", "fb_automation.db")
db = SqliteDatabase(DB_PATH)


class BaseModel(Model):
    class Meta:
        database = db


class ContentItem(BaseModel):
    """A piece of content discovered from RSS — before it becomes a post."""

    class Meta:
        table_name = "content_items"

    id              = CharField(primary_key=True)   # md5 of title
    niche           = CharField()                   # crime | finance | weird
    title           = CharField()
    summary         = TextField(default="")
    source_url      = CharField(default="")
    image_url       = CharField(default="")         # original news image
    discovered_at   = DateTimeField(default=datetime.utcnow)
    used            = BooleanField(default=False)


class ScheduledPost(BaseModel):
    """A post ready to go — image generated, caption written, waiting to fire."""

    class Meta:
        table_name = "scheduled_posts"

    id              = CharField(primary_key=True)
    page_id         = CharField()
    niche           = CharField()
    caption         = TextField()
    image_path      = CharField(default="")         # local path to generated image
    canva_image_url = CharField(default="")         # Canva export URL
    scheduled_at    = DateTimeField()               # UTC time to post
    posted          = BooleanField(default=False)
    post_id         = CharField(default="")         # Facebook post ID after posting
    error           = TextField(default="")
    created_at      = DateTimeField(default=datetime.utcnow)


class PostPerformance(BaseModel):
    """Tracks reach and engagement — checked 24h after posting."""

    class Meta:
        table_name = "post_performance"

    post_id         = CharField(primary_key=True)   # Facebook post ID
    page_id         = CharField()
    niche           = CharField()
    reach           = IntegerField(default=0)
    impressions     = IntegerField(default=0)
    reactions       = IntegerField(default=0)
    shares          = IntegerField(default=0)
    comments        = IntegerField(default=0)
    checked_at      = DateTimeField(default=datetime.utcnow)


def init_db():
    db.connect(reuse_if_open=True)
    db.create_tables([ContentItem, ScheduledPost, PostPerformance], safe=True)
    db.close()
