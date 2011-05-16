{-
    Copyright (C) 2010 Stanislav Bohm

    This file is part of Kaira.

    Kaira is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, version 3 of the License, or
    (at your option) any later version.

    Kaira is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with Kaira.  If not, see <http://www.gnu.org/licenses/>.
-}

module CodegenTypes where

import Declarations

import qualified Data.Set as Set
import qualified Data.Map as Map

data Type = TUndefined |
			TVoid |
			TInt |
			TFloat |
			TDouble |
			TString |
			TBool |
			TTuple [Type] |
			TArray Type |
			TPlace Type |
			TRaw String |
			TPointer Type |
			TData String String TransportMode [ (String, String) ] | {- name, rawName, transportMode, functions -}
			TStruct String [VarDeclaration] |
			TClass String (Maybe String) [Function] [VarDeclaration] {- name, ancestor, methods, decls -}
	deriving (Show, Eq, Ord)

type VarDeclaration = (String, Type)
type ParamDeclaration = (String, Type, ParamType)
type FunDeclaration = (String, Type, [Type])
type TypeSet = Set.Set Type

data Declarations = Declarations {
	varDeclarations :: [VarDeclaration],
	funDeclarations :: [FunDeclaration]
} deriving (Show, Eq)


data Expression =
	ECall String [Expression] |
	EVar String |
	EType String |
	EInt Int |
	EString String |
	ETuple [Expression] |
	EAddr Expression |
	EAt Expression Expression {- index container -} |
	EDeref Expression |
	ECast Expression Type |
	ETrue | ExprFalse |
	ENew Expression
	deriving (Show, Eq, Ord)

data Instruction =
	IExpr Expression |
	ISet Expression Expression |
	IIf Expression Instruction Instruction |
	IForeach String String Expression [Instruction] | {- var counterVar array body -}
	IStatement [Instruction] |
	IDefine String Type (Maybe Expression) |
	IReturn Expression |
	IContinue |
	IInline String |
	INoop
	deriving (Show, Eq, Ord)


data Function = Function {
	functionName :: String,
	instructions :: [Instruction],
	parameters :: [ParamDeclaration],
	extraCode :: String,
	returnType :: Type,
	functionSource :: Maybe (String, Int),
	initCall :: Maybe Expression
} deriving (Show, Eq, Ord)

