
import asyncio
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-3.8-flash",
    max_retries=3,
    timeout=20,
)

MAX_CONCURRENT_IMAGES = 4


async def describe_one_image(
    url: str,
    semaphore: asyncio.Semaphore,
) -> str:
    async with semaphore:
        try:
            # Skip SVG images
            if ".svg" in url.lower().split("?")[0]:
                return ""

            message = HumanMessage(
                content=[
                    {
                        "type": "text",
                        "text": (
                            "Describe this image in one concise sentence. "
                            "Capture its main subject, important details, "
                            "and any visible text. Do not guess."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": url},
                    },
                ]
            )

            response = await asyncio.wait_for(
                llm.ainvoke([message]),
                timeout=25,
            )

            content = response.content

            if isinstance(content, str):
                return content.strip()

            if isinstance(content, list):
                return " ".join(
                    item["text"]
                    for item in content
                    if isinstance(item, dict)
                    and isinstance(item.get("text"), str)
                ).strip()

            return str(content).strip()

        except Exception as e:
            print(f"Image error ({url}): {e}")
            return ""


async def describe_img(img_urls: list[str]) -> str:
    # Remove duplicate URLs while preserving order
    unique_urls = list(dict.fromkeys(img_urls))

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_IMAGES)

    results = await asyncio.gather(
        *[
            describe_one_image(url, semaphore)
            for url in unique_urls
        ]
    )

    descriptions = [
        description
        for description in results
        if description
    ]

    return "\n".join(descriptions)



