# test_indictrans.py
try:
    from indictrans2 import Transliterator
    print("IndicTrans2 imported successfully!")
except ModuleNotFoundError:
    print("ModuleNotFoundError: indictrans2 not found")
except Exception as e:
    print(f"Some other error occurred: {e}")
