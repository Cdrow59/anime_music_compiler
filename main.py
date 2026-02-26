import mal_client
import animethemes_client
import pprint
from database import init_db, insert_anime

mal_client_instance = mal_client.MALClient(per_second=1)
anime_themes_client_instance = animethemes_client.ATClient(per_minute=90)

anime_list = mal_client_instance.get_user_anime_list("Cdrow")

conn = init_db("anime.db")
for item in anime_list:
    node = item.get("node")
    if node and "id" in node:
        anime_id = node["id"]
        anime_title = node["title"]

        data = mal_client_instance.get_anime(
            anime_id, fields="id,title,opening_themes,ending_themes"
        )

        insert_anime(conn, data)


conn.close()
print("Import complete.")
