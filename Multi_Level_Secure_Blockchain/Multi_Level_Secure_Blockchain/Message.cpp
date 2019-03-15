//
//  Message.cpp
//  Multi_Level_Secure_Blockchain
//
//  Created by Kendric Hood on 3/8/19.
//  Copyright © 2019 Kent State University. All rights reserved.
//

#include "Packet.hpp"

//
// Base message definitions
//
template<class T>
Packet<T>::Packet(int id){
    _id = id;
    _targetId = "";
    _sourceId = "";
    _delay = rand()%_DELAY_UPPER_BOUND;
}

template<class T>
Packet<T>::Packet(int id, std::string from){
    _id = id;
    _sourceId = from;
    
    srand((float)time(NULL));
    _delay = rand()%_DELAY_UPPER_BOUND;;
}

template<class T>
Packet<T>::Packet(const Message& rhs){
    _id = rhs._id;
    _targetId = rhs._targetId;
    _sourceId = rhs._sourceId;
}

template<class T>
Packet<T>::~Packet(){
    // no memory allocated so nothing to do
}

template<class T>
Packet<T>& Packet<T>::operator=(const Message &rhs){
    _id = rhs._id;
    _targetId = rhs._targetId;
    _sourceId = rhs._sourceId;
    return *this;
}

template<class T>
bool Packet<T>::operator==(const Message &rhs){
    return _id == rhs._id;
}

template<class T>
bool Packet<T>::operator!=(const Message &rhs){
    return !(*this == rhs);
}
