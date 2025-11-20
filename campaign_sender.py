#!/usr/bin/env python3
"""
Campaign Sender Worker - Send emails for running campaigns
Processes PENDING emails for all running campaigns, respecting daily limits and delays
"""

import logging
import time
import requests
from datetime import datetime, timedelta
from typing import List, Dict
import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from campaign_database import (
    get_campaign_session, Campaign, CampaignStatus, CampaignEmail, EmailStatus
)

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Flask API configuration
API_BASE_URL = "http://127.0.0.1:5002"


class CampaignSender:
    """Worker to send emails for running campaigns"""

    def __init__(self):
        """Initialize the worker"""
        self.session = get_campaign_session()
        logger.info("✅ Campaign Sender Worker initialized")

    def get_running_campaigns(self) -> List[Campaign]:
        """
        Get all running campaigns (both normal and continuous)

        Returns:
            List of running campaigns
        """
        campaigns = self.session.query(Campaign).filter(
            Campaign.status == CampaignStatus.RUNNING
        ).all()

        return campaigns

    def get_pending_count(self, campaign_id: int) -> int:
        """
        Get count of pending emails for a campaign

        Args:
            campaign_id: Campaign ID

        Returns:
            Number of pending emails
        """
        count = self.session.query(CampaignEmail).filter(
            CampaignEmail.campaign_id == campaign_id,
            CampaignEmail.status == EmailStatus.PENDING
        ).count()

        return count

    def get_sent_today_count(self, campaign_id: int) -> int:
        """
        Get count of emails sent today for a campaign

        Args:
            campaign_id: Campaign ID

        Returns:
            Number of emails sent today
        """
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        count = self.session.query(CampaignEmail).filter(
            CampaignEmail.campaign_id == campaign_id,
            CampaignEmail.sent_at >= today_start,
            CampaignEmail.status.in_([
                EmailStatus.SENT,
                EmailStatus.DELIVERED,
                EmailStatus.OPENED,
                EmailStatus.CLICKED
            ])
        ).count()

        return count

    def send_batch_for_campaign(self, campaign: Campaign) -> Dict:
        """
        Send a batch of emails for a campaign

        Args:
            campaign: Campaign to process

        Returns:
            Result dictionary
        """
        logger.info(f"🔄 Processing campaign '{campaign.name}' (ID: {campaign.id})")

        try:
            # Check if we're in the allowed time window (9 AM - 6 PM UTC)
            current_hour = datetime.now().hour
            if current_hour < 9 or current_hour >= 18:
                logger.info(f"   ⏰ Outside sending hours (9 AM - 6 PM UTC). Current time: {current_hour}:00")
                return {
                    'campaign_id': campaign.id,
                    'campaign_name': campaign.name,
                    'pending': self.get_pending_count(campaign.id),
                    'sent': 0,
                    'outside_hours': True
                }

            # Check pending emails
            pending_count = self.get_pending_count(campaign.id)

            if pending_count == 0:
                logger.info(f"   ℹ️  No pending emails for '{campaign.name}'")
                return {
                    'campaign_id': campaign.id,
                    'campaign_name': campaign.name,
                    'pending': 0,
                    'sent': 0
                }

            # Check daily quota
            sent_today = self.get_sent_today_count(campaign.id)
            remaining_quota = campaign.max_emails_per_day - sent_today

            if remaining_quota <= 0:
                logger.info(f"   ⚠️  Daily quota reached for '{campaign.name}' ({sent_today}/{campaign.max_emails_per_day})")
                return {
                    'campaign_id': campaign.id,
                    'campaign_name': campaign.name,
                    'pending': pending_count,
                    'sent': 0,
                    'quota_reached': True
                }

            # Calculate batch size (max 50 per API call, respecting quota)
            batch_size = min(50, remaining_quota, pending_count)

            logger.info(f"   📬 {pending_count} pending emails, sending batch of {batch_size}")
            logger.info(f"   📊 Quota: {sent_today}/{campaign.max_emails_per_day} (remaining: {remaining_quota})")

            # Call Flask API to send emails
            url = f"{API_BASE_URL}/api/campaigns/{campaign.id}/send"
            response = requests.post(url, json={'limit': batch_size}, timeout=60)

            if response.status_code == 200:
                result = response.json()
                sent_count = result.get('sent', 0)
                logger.info(f"   ✅ Sent {sent_count} emails for '{campaign.name}'")

                return {
                    'campaign_id': campaign.id,
                    'campaign_name': campaign.name,
                    'pending': pending_count,
                    'sent': sent_count,
                    'quota_reached': False
                }
            else:
                logger.error(f"   ❌ API error: {response.status_code} - {response.text}")
                return {
                    'campaign_id': campaign.id,
                    'campaign_name': campaign.name,
                    'pending': pending_count,
                    'sent': 0,
                    'error': f"API error: {response.status_code}"
                }

        except Exception as e:
            logger.error(f"   ❌ Error processing campaign '{campaign.name}': {str(e)}", exc_info=True)
            return {
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'error': str(e)
            }

    def run_once(self):
        """Execute one iteration of the worker"""
        logger.info("=" * 80)
        logger.info("🚀 Starting campaign sender cycle")
        logger.info("=" * 80)

        try:
            # Get all running campaigns
            campaigns = self.get_running_campaigns()

            if not campaigns:
                logger.info("ℹ️  No running campaigns")
                return

            logger.info(f"📋 {len(campaigns)} running campaign(s) found")

            # Process each campaign
            results = []
            for campaign in campaigns:
                result = self.send_batch_for_campaign(campaign)
                results.append(result)

                # Respect campaign delay between batches
                if campaign.delay_between_emails:
                    delay = campaign.delay_between_emails * 50  # 50 emails in batch
                    logger.info(f"   ⏸️  Waiting {delay}s before next campaign...")
                    time.sleep(delay)
                else:
                    time.sleep(5)  # Default 5 second pause

            # Summary
            logger.info("=" * 80)
            logger.info("📊 Cycle summary:")
            total_sent = sum(r.get('sent', 0) for r in results)
            total_pending = sum(r.get('pending', 0) for r in results)
            quota_reached_count = sum(1 for r in results if r.get('quota_reached', False))

            logger.info(f"   - Total emails sent: {total_sent}")
            logger.info(f"   - Total emails pending: {total_pending}")
            logger.info(f"   - Campaigns with quota reached: {quota_reached_count}")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"❌ Error during cycle: {str(e)}", exc_info=True)

    def run(self, interval_minutes: int = 5):
        """
        Run the worker continuously

        Args:
            interval_minutes: Interval between executions (in minutes)
        """
        logger.info("=" * 80)
        logger.info("🎬 STARTING CAMPAIGN SENDER WORKER")
        logger.info(f"⏱️  Interval: {interval_minutes} minutes")
        logger.info("=" * 80)

        while True:
            try:
                self.run_once()

                # Wait before next execution
                logger.info(f"⏸️  Next execution in {interval_minutes} minutes...")
                time.sleep(interval_minutes * 60)

            except KeyboardInterrupt:
                logger.info("🛑 Worker stopped by user")
                break
            except Exception as e:
                logger.error(f"❌ Critical error: {str(e)}", exc_info=True)
                logger.info("⏸️  Waiting 5 minutes before retry...")
                time.sleep(300)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Campaign sender worker')
    parser.add_argument(
        '--interval',
        type=int,
        default=5,
        help='Interval between executions (in minutes, default: 5)'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Execute once and exit'
    )

    args = parser.parse_args()

    worker = CampaignSender()

    if args.once:
        logger.info("Mode: single execution")
        worker.run_once()
    else:
        logger.info("Mode: continuous execution")
        worker.run(interval_minutes=args.interval)


if __name__ == '__main__':
    main()
