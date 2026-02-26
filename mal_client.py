import os
import logging
from dotenv import load_dotenv
from requests import Session
from requests_cache import CacheMixin
from requests_ratelimiter import LimiterMixin, SQLiteBucket
from pprint import pprint

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


class CachedLimiterSession(CacheMixin, LimiterMixin, Session):
    """
    Session class with caching and rate-limiting behavior. Accepts arguments for both
    LimiterSession and CachedSession.
    """


class MALClient:
    def __init__(self, per_second):
        self.client_id = os.getenv("MAL_CLIENT_ID")
        self.client_secret = os.getenv("MAL_CLIENT_SECRET")
        self.headers = {"X-MAL-CLIENT-ID": self.client_id}
        self.base_url = "https://api.myanimelist.net/v2"

        # Rate-limited session
        self.session = CachedLimiterSession(
            cache_name="mal_cache",
            backend="sqlite",
            expire_after=60 * 60 * 24,  # sec * mins * hours
            per_second=per_second,
            limit_statuses=[429, 504],
            bucket_class=SQLiteBucket,
            bucket_kwargs={
                "path": "mal_cache.sqlite",
                "isolation_level": "EXCLUSIVE",
                "check_same_thread": False,
            },
        )
        logger.info("Initialized MALClient with rate limit %s req/sec", per_second)

    def get_anime(self, anime_id: int, fields: str = None):
        """Fetch anime details by ID"""
        url = f"{self.base_url}/anime/{anime_id}"
        params = {"fields": fields} if fields else None
        try:
            response = self.session.get(url, params=params, headers=self.headers)
            response.raise_for_status()
            logger.info("Successfully fetched anime ID %s", anime_id)
            return response.json()
        except Exception as e:
            logger.error("Error fetching anime ID %s: %s", anime_id, e)
            raise

    def get_user_anime_list(self, user_name: str, **extra_params):
        """Fetch all anime from a user's list with paging"""
        url = f"{self.base_url}/users/{user_name}/animelist"
        all_results = []
        params = {k: v for k, v in extra_params.items() if v is not None}
        logger.info(
            "Fetching anime list for user '%s' with params: %s", user_name, params
        )

        while url:
            try:
                response = self.session.get(url, params=params, headers=self.headers)
                response.raise_for_status()
                data = response.json()

                all_results.extend(data.get("data", []))
                logger.info(
                    "Fetched %s items, next page: %s",
                    len(data.get("data", [])),
                    data.get("paging", {}).get("next"),
                )

                url = data.get("paging", {}).get("next")
                params = None  # next URL already has query params
            except Exception as e:
                logger.error("Error fetching user anime list: %s", e)
                raise

        logger.info(
            "Completed fetching anime list for user '%s', total items: %s",
            user_name,
            len(all_results),
        )
        return all_results
