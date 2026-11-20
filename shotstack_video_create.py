import requests

def generisi_video_preko_shotstack(audio_url, naslov_vijesti):
    url = "https://api.shotstack.io/v1/render"
    headers = {
        "x-api-key": "UTZONMq003WYSUFFa5IgJm6AhNj7MqVUXcxfh3Mq",
        "Content-Type": "application/json"
    }
    
    # JSON koji opisuje video
    video_data = {
        "timeline": {
            "tracks": [
                {
                    "clips": [
                        {
                            "asset": {
                                "type": "title",
                                "text": naslov_vijesti,
                                "style": "minimal"
                            },
                            "start": 0,
                            "length": 5
                        }
                    ]
                },
                {
                    "clips": [
                        {
                            "asset": {
                                "type": "audio",
                                "src": audio_url
                            },
                            "start": 0,
                            "length": 5
                        }
                    ]
                }
            ]
        },
        "output": {
            "format": "mp4",
            "resolution": "sd" # Besplatni plan podržava SD ili HD sa žigom
        }
    }

    response = requests.post(url, json=video_data, headers=headers)
    return response.json()
