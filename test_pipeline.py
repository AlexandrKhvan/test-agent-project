from ingestion.document_parsers import extract_text
from curriculum.architect_agent import generate_curriculum
from dotenv import load_dotenv

# Загружаем ключи
load_dotenv()

def run_test():
    print("1. Тестируем парсер (Агент 1)...")
    # Подставь путь к любому реальному тестовому PDF
    raw_text = extract_text("data/sample_materials/sample_1.pdf", "pdf")
#    raw_text = extract_text("data/sample_materials/sample_image_1.png", "png")
    
    if not raw_text:
        print("❌ Ошибка: Парсер вернул пустую строку.")
        return
        
    print(f"✅ Парсер отработал. Извлечено {len(raw_text)} символов.")
    print("Первые 100 символов:", raw_text[:100], "...\n")
    
    print("2. Тестируем архитектора курса (Агент 2)...")
    try:
        curriculum = generate_curriculum(raw_text)
        print("✅ Архитектор отработал успешно!")
        print(f"Название курса: {curriculum.title}")
        print(f"Концепции: {curriculum.key_concepts}")
        print(f"Количество квизов: {len(curriculum.quiz)}")
    except Exception as e:
        print(f"❌ Ошибка Агента 2: {e}")

if __name__ == "__main__":
    run_test()