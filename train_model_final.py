from pygrowup import Calculator

class MalnutritionModel:
    def __init__(self):
        # Initialize WHO standards calculator
        # adjust_height_data=False: We assume you input the correct measurement (Length for <2y, Height for >2y)
        self.calculator = Calculator(adjust_height_data=False, adjust_weight_scores=False)

    def predict(self, weight_kg, height_cm, age_years, sex, edema=False):
        """
        Classifies malnutrition for children under 5 years.
        This method is called by app.py.
        """
        
        # 1. CRITICAL RULE: Edema = SAM immediately
        if edema:
            return {
                "status": "Severe Acute Malnutrition (SAM)",
                "z_score": -5.0, # Dummy low score for edema
                "color_code": "RED",
                "action": "Urgent Medical Attention Required (Edematous Malnutrition)"
            }

        # 2. Convert Age to what the WHO calculator expects (months)
        age_months = age_years * 12

        # 3. Sex standardization
        sex_code = 'M' if sex.lower().startswith('m') else 'F'

        try:
            # 4. Calculate Weight-for-Height/Length Z-score (WHZ)
            # Note: valid for children 0-60 months (0-5 years)
            whz = self.calculator.wfl(weight_kg, age_months, sex_code, height_cm)
            
        except Exception as e:
            # Return a safe error dict that app.py can handle
            return {
                "status": "Error",
                "message": f"Could not calculate score: {str(e)}",
                "z_score": 0,
                "color_code": "GRAY",
                "action": "Check Inputs"
            }

        # 5. Classify based on WHO Z-score cutoffs
        if whz < -3:
            status = "Severe Acute Malnutrition (SAM)"
            color = "RED"
            action = "Urgent Treatment Needed"
        elif -3 <= whz < -2:
            status = "Moderate Acute Malnutrition (MAM)"
            color = "YELLOW"
            action = "Supplementary Feeding Required"
        elif -2 <= whz < 2:
            status = "Normal"
            color = "GREEN"
            action = "Maintain Healthy Diet"
        else:
            status = "Possible Overweight"
            color = "ORANGE"
            action = "Monitor Diet"

        return {
            "status": status,
            "z_score": round(whz, 2),
            "color_code": color,
            "action": action
        }

# Create a single instance to be imported by app.py
model = MalnutritionModel()