import math
import tools

class Habitat(float): 
    NAMES = ['Cold', 'Warm', 'Shallow', 'Deep', 'Fresh', 'Salt', 'Reef'] 
    MAX = 2**len(NAMES) - 1

    @staticmethod
    def convert_to_base(num, base) -> list[int]: 
        assert num >= 0

        if num == 0: 
            conversion = [0] 
        else: 
            power = int(math.log(num, base)) 
            conversion = [] 

            while power >= 0: 
                quotient, remainder = divmod(num, base**power) 

                conversion.insert(0, quotient) 
                num = remainder

                power -= 1
            
        return conversion

    def convert_to_list(self): 
        conversion = self.convert_to_base(int(self), 2) 

        #print(conversion) 

        length = len(conversion) 

        partial_display = [] 

        for index in range(0, length, 2): 
            #print(index) 

            next_index = index + 1

            current_flag = conversion[index] 
            current_name = self.NAMES[index] if current_flag else False

            #print(current_name) 
            
            if next_index >= length: 
                next_flag = False
            else: 
                next_flag = conversion[next_index] 
            
            next_name = self.NAMES[next_index] if next_flag else False

            #print(next_name) 

            if current_name and next_name: 
                string = f'{current_name}/{next_name}' 
            else: 
                string = current_name or next_name
            
            #print(string) 
            
            if string: 
                partial_display.append(string) 
        
        return partial_display
    
    def has_reef(self):
        return self >= 2**(len(self.NAMES) - 1)
    
    def valid_and_liveable(self):
        if self.valid():
            converted = self.convert_to_list()

            return len(converted) == 4 or not self.has_reef() and len(converted) == 3
        else:
            return False

    def __str__(self): 
        if self.valid(): 
            display = tools.format_iterable(self.convert_to_list()) 
        else: 
            display = f'invalid habitat ({self!r})' 

        return display
    
    def valid(self):
        return math.isfinite(self) and int(self) == self and 0 <= self <= self.MAX

num = 0

thing = Habitat(102 + num) 

print(thing) 