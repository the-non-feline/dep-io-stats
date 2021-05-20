import math
import tools

class Habitat(int): 
    NAMES = ['Cold', 'Warm', 'Shallow', 'Deep', 'Fresh', 'Salt', 'Reef'] 

    @staticmethod
    def convert_to_base(num, base): 
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

    def __str__(self): 
        len_flags = len(self.NAMES) 

        if 0 <= self < 2**len_flags: 
            conversion = self.convert_to_base(self, 2) 

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
            
            display = tools.format_iterable(partial_display) 
        else: 
            display = f'invalid habitat ({self!r})' 

        return display

num = -16

thing = Habitat(111 + num) 

print(thing) 