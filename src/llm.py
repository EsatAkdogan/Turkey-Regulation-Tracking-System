import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

class LLMSummarizer:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash') 

    def summarize(self, text):
        if not self.api_key:
            return f"[DEMO] {text[:100]}... (API Key missing. Please set GEMINI_API_KEY in .env)"
        
        try:
            prompt = f"""
            You are an expert assistant summarizing legal texts for lawyers and startups.
            Summarize the following text in a clear and action-oriented manner:

            {text}
            """
            
            try:
                response = self.model.generate_content(prompt)
                return response.text
            except Exception as e:
                # switch lite model on limit
                if "429" in str(e) or "quota" in str(e).lower():
                    fallback_model = genai.GenerativeModel('gemini-2.0-flash-lite')
                    response = fallback_model.generate_content(prompt)
                    return response.text
                raise e
                    
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                return "ERROR: Gemini API quota exceeded. Please wait 1-2 minutes and try again."
            return f"Gemini Error: {str(e)}"
