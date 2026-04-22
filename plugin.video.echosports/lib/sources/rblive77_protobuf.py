# -*- coding: utf-8 -*-
"""
Minimal Protobuf Parser for RBLive77 API responses.

Wire format reference: https://protobuf.dev/programming-guides/encoding/

We only need to parse the specific structure from RBLive77:
- Field 3: string (status message)
- Field 10: nested message (data container)
  - Field 1: repeated message (match array)
    - Field 1: int (matchId)
    - Field 2: int (sportType)
    - Field 3: int (startTime ms)
    - Field 90: int (hasStream)
    - And other fields as needed

This is a simplified parser that skips unknown fields.
"""

import struct
from typing import Dict, List, Any, Optional, Tuple


class ProtobufParser:
    """Minimal protobuf wire format parser."""
    
    # Wire types
    VARINT = 0
    FIXED64 = 1
    LENGTH_DELIMITED = 2
    START_GROUP = 3  # Deprecated
    END_GROUP = 4    # Deprecated
    FIXED32 = 5
    
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0
        
    def read_varint(self) -> int:
        """Read a variable-length integer."""
        result = 0
        shift = 0
        while True:
            if self.pos >= len(self.data):
                raise ValueError("Unexpected end of data")
            byte = self.data[self.pos]
            self.pos += 1
            result |= (byte & 0x7F) << shift
            if not (byte & 0x80):
                break
            shift += 7
        return result
        
    def read_tag(self) -> Optional[Tuple[int, int]]:
        """Read a field tag. Returns (field_number, wire_type) or None if at end."""
        if self.pos >= len(self.data):
            return None
        tag = self.read_varint()
        field_number = tag >> 3
        wire_type = tag & 0x7
        return (field_number, wire_type)
        
    def read_length_delimited(self) -> bytes:
        """Read a length-prefixed byte array."""
        length = self.read_varint()
        if self.pos + length > len(self.data):
            raise ValueError("Length exceeds data bounds")
        result = self.data[self.pos:self.pos + length]
        self.pos += length
        return result
        
    def read_fixed32(self) -> int:
        """Read a 32-bit fixed-length integer."""
        if self.pos + 4 > len(self.data):
            raise ValueError("Not enough data for fixed32")
        result = struct.unpack('<I', self.data[self.pos:self.pos + 4])[0]
        self.pos += 4
        return result
        
    def read_fixed64(self) -> int:
        """Read a 64-bit fixed-length integer."""
        if self.pos + 8 > len(self.data):
            raise ValueError("Not enough data for fixed64")
        result = struct.unpack('<Q', self.data[self.pos:self.pos + 8])[0]
        self.pos += 8
        return result
        
    def skip_field(self, wire_type: int):
        """Skip a field based on its wire type."""
        if wire_type == self.VARINT:
            self.read_varint()
        elif wire_type == self.FIXED64:
            self.read_fixed64()
        elif wire_type == self.LENGTH_DELIMITED:
            self.read_length_delimited()
        elif wire_type == self.FIXED32:
            self.read_fixed32()
        else:
            raise ValueError(f"Unknown wire type: {wire_type}")
            
    def parse_message(self) -> Dict[int, Any]:
        """
        Parse a protobuf message into a dict.
        Keys are field numbers, values are field values.
        """
        result = {}
        
        while True:
            tag_info = self.read_tag()
            if tag_info is None:
                break
                
            field_number, wire_type = tag_info
            
            if wire_type == self.VARINT:
                value = self.read_varint()
                result[field_number] = value
                
            elif wire_type == self.LENGTH_DELIMITED:
                data = self.read_length_delimited()
                # Try to decode as string (UTF-8)
                try:
                    value = data.decode('utf-8')
                    result[field_number] = value
                except UnicodeDecodeError:
                    # It's a nested message or bytes
                    # Special case: Don't parse field 1 here if we're inside field 10
                    # (it's a repeated field that needs special handling)
                    # We detect this by checking if result is empty or has only field numbers < 10
                    # This is a heuristic: field 10 is typically early in the message
                    is_likely_field_10 = (field_number == 1 and 
                                         len(result) <= 3 and 
                                         all(k < 15 for k in result.keys()))
                    
                    if is_likely_field_10:
                        # Store as raw bytes for special handling later
                        result[field_number] = data
                    else:
                        # Try to parse as nested message
                        try:
                            parser = ProtobufParser(data)
                            nested = parser.parse_message()
                            result[field_number] = nested
                        except:
                            # Can't parse as message, store as bytes
                            result[field_number] = data
                        
            elif wire_type == self.FIXED64:
                value = self.read_fixed64()
                result[field_number] = value
                
            elif wire_type == self.FIXED32:
                value = self.read_fixed32()
                result[field_number] = value
                
            else:
                # Unknown wire type, skip
                self.skip_field(wire_type)
                
        return result
        
    def parse_repeated_field(self, data: bytes) -> List[Dict]:
        """
        Parse a repeated field (array of messages).
        Each message is length-delimited.
        """
        parser = ProtobufParser(data)
        result = []
        
        while parser.pos < len(parser.data):
            # Each item is a length-delimited message
            item_data = parser.read_length_delimited()
            item_parser = ProtobufParser(item_data)
            item = item_parser.parse_message()
            result.append(item)
            
        return result


def parse_rblive77_response(data: bytes) -> Optional[Dict]:
    """
    Parse RBLive77 API response.
    
    Expected structure:
    {
      3: "Success",  # string
      10: {          # nested message
        1: [...]     # repeated messages (matches)
      }
    }
    
    Args:
        data: Raw protobuf bytes
        
    Returns:
        Parsed dict with integer keys, or None on error
    """
    try:
        parser = ProtobufParser(data)
        message = parser.parse_message()
        
        # Field 10 contains the data container
        if 10 in message and isinstance(message[10], dict):
            data_container = message[10]
            # Field 1 within field 10 is the match array (bytes)
            if 1 in data_container and isinstance(data_container[1], bytes):
                # Parse the repeated field
                match_parser = ProtobufParser(data_container[1])
                matches = []
                
                # Read each match as a length-delimited message
                while match_parser.pos < len(match_parser.data):
                    try:
                        match_data = match_parser.read_length_delimited()
                        match_parser_inner = ProtobufParser(match_data)
                        match = match_parser_inner.parse_message()
                        matches.append(match)
                    except:
                        break
                        
                # Replace the bytes with parsed array
                data_container[1] = matches
                
        return message
        
    except Exception as e:
        import xbmc
        xbmc.log(f"[RBLive77] Protobuf parse error: {e}", xbmc.LOGERROR)
        return None
