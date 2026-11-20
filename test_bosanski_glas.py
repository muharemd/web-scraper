import asyncio
import edge_tts

async def test_bihac():
    # 'bs-BA-VesnaNeural' je standard za bosanski
    # 'hr-HR-SreckoNeural' je odličan muški glas koji zvuči vrlo prirodno za vijesti
    tekst = "Dobrodošli na kanal Bihać Danas. Donosimo vam najnovije vijesti iz našeg grada i kantona."
    
    communicate = edge_tts.Communicate(tekst, "hr-HR-SreckoNeural")
    await communicate.save("bihac_vijesti.mp3")
    print("Fajl je spreman!")

if __name__ == "__main__":
    asyncio.run(test_bihac())
